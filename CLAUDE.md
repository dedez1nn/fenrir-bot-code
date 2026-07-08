# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the bot (local dev):**
```bash
python main.py
```

**Run with Docker (3 services: postgres + bot + api):**
```bash
docker compose up --build
# or only Postgres for local dev against `python main.py`:
docker compose up -d postgres
```

**Apply migrations + import legacy JSONs (standalone, outside the bot):**
```bash
python -m scripts.db_setup            # apply + import
python -m scripts.db_setup --no-import
```

**Install dependencies:**
```bash
pip install -r requirements.txt        # bot
pip install -r api/requirements.txt    # api (separate process)
```

**Run all tests:**
```bash
pytest
```

Current verified state: `pytest -q` passes with `162 passed` and warnings. The main warnings are `datetime.utcnow()` deprecations and some `RuntimeWarning` noise around mocked `tasks.loop` usage in tests.

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `TOKEN` — Discord bot token
- `ACCESS_TOKEN` — Mercado Pago access token
- `POSTGRES_PASSWORD` — Postgres password
- `DATABASE_URL` — connection string. In docker-compose the host is `postgres`; for `python main.py` against a locally-exposed Postgres, use `localhost:5432`.
- `JWT_SECRET` — sign admin panel session tokens (`openssl rand -hex 32`). Leave as default `change-me-in-production` in dev to disable auth checks.
- `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` / `DISCORD_REDIRECT_URI` — Discord OAuth2 app credentials for the admin panel login.
- `ADMIN_ROLE_IDS` — comma-separated Discord role IDs allowed to access the panel. Empty = any guild member.
- `MP_WEBHOOK_SECRET` — Mercado Pago webhook signing secret for HMAC validation.

The bot **does not crash if Postgres is unavailable** — it logs a warning and operates in legacy-JSON mode. JSON files remain fallback for the migrated systems as well, including guilds and adventures.

## Architecture

**Entry point:** `main.py` creates a `FenrirBot(commands.Bot)` with prefix `!` and all intents. On `setup_hook` it:
1. Calls `_init_database()` — initializes `bot.db` (asyncpg pool), applies migrations from `db/migrations/*.sql`, imports legacy JSONs into the DB if the target tables are empty, and loads `bot.config` (a `ServerConfig` cached for 5 min).
2. Walks `cogs/` and loads extensions. **The walker has special handling for cog-packages**: if a directory has `__init__.py` defining `setup()` (e.g. `cogs/antispam`, `cogs/antinuke`), it's loaded once as a package and submodules are *not* loaded as separate cogs. Directories with empty `__init__.py` (e.g. `cogs/economia/`) keep the old behavior — each `.py` is its own cog.
3. Syncs slash commands with `tree.sync()`.
4. Calls `_start_cache_listener()` — registers `pool.add_listener("fenrir_cache", …)` to receive PostgreSQL NOTIFY events from the API. Full payload contract:
   - `user:{id}` — reload user cache in FenrirCoins/XPCog
   - `premium:{id}:{plano}` — reload cache + call `PixCog.grant_premium_rewards`
   - `config:{guild_id}` — reload `server_config`
   - `antispam:{guild_id}` — call `AntiSpam.reload_config_from_db`
   - `antinuke:{guild_id}` — call `AntiNuke.reload_config_from_db`
   - `feature:{guild_id}:{feature}` — call `cog.reload_feature_state()` on the cog mapped in `_FEATURE_COG_MAP` (main.py)

On `on_ready`, it posts/refreshes persistent embeds in fixed channels (status, colors, pix plans, tickets) — all channel IDs are resolved via `bot.config.get("key")` (Phase 2 complete).

**Current operating model:** all extensions under `cogs/` with `setup()` are auto-loaded at startup, so most features are effectively enabled by default unless they self-degrade because of missing config, missing permissions, or missing external credentials. The system is only partially configuration-driven today; some areas already use `server_config` and feature-specific tables, while others still depend on hardcoded IDs and defaults.

**Cog system:** Each entry-point module (file or package with `setup()` in `__init__.py`) defines `async def setup(bot)`. Cogs communicate with each other via `bot.get_cog("CogName")` — always check for `None`. Cogs that need the database access `bot.db` (the asyncpg pool) and `bot.config` (the cached `ServerConfig`); both can be `None` in degraded mode.

**Branches (post-unification):**
- **`main`** — unified bot: economy, XP, guilds, shop, Mercado Pago, Riot/Steam/GNews APIs **plus** antinuke, antispam, invite blocker, auto-remove bots. The current loader finds **26 extension entry points** with `setup()`.
- **`fenrir_security`** — historical branch; no longer the source of truth. Kept for git archeology.

**Cogs ported in Phase 1:**
- `cogs/antinuke/` — detects mass bans/kicks/channel deletes, escalates severity (log → ping → slowmode → lockdown). Config (`AntinukeConfig`) loads from `antinuke_config` table on `cog_load`, falls back to defaults.
- `cogs/antispam/` — scores messages for flood, duplicate, phishing, mentions, caps, promo spam. Punishes via ladder (warn → timeout → kick → ban). Config (`AntispamConfig`) loads from `antispam_config` table. Storage uses `PgStorage` (Postgres-backed) when `bot.db` is available; falls back to `JSONStorage` (`data/antispam.json`) when it isn't.
- `cogs/block_inv.py` — deletes Discord invites from other servers, notifies the user via DM.
- `cogs/security.py` — auto-kicks unauthorized bots on join.

## Data layer

**`db/` package** — managed Postgres access:
- `db/pool.py` — `init_pool()` returns the asyncpg `Pool` or `None` on failure. Registers a `jsonb`/`json` codec on every connection so JSONB columns round-trip as Python `dict`/`list` (not strings).
- `db/config.py` — `ServerConfig` exposes config fields by attribute and `[]`. `load_server_config(pool, guild_id)` and `refresh_server_config(pool, guild_id)` (called by API after PATCHing config).
- `db/migrate.py` — `apply_migrations(pool)` runs every `db/migrations/*.sql` in order, recording each in `schema_migrations`. Idempotent. `import_legacy_json(pool)` populates `users`/`items`/`cooldowns` from `data/*.json` when those tables are empty.
- `db/migrations/001_initial.sql` — full schema (10 tables).
- `db/migrations/002_seed.sql` — initial `server_config` row with the current hardcoded IDs.

**`api/` package** — FastAPI (Phases 0–5). Routers registrados:
- `/health` — liveness + readiness (ping DB)
- `/auth/*` — Discord OAuth2 (`/authorize`, `/callback`, `/logout`, `/me`). Dependência `require_admin` exportada de `api/routers/auth.py`; em desenvolvimento (JWT_SECRET padrão) a validação é dispensada automaticamente.
- `/webhooks/mercadopago` — valida HMAC `x-signature`, processa pagamento aprovado em background, atualiza `users.premium` e envia `pg_notify('fenrir_cache', 'premium:{id}:{plano}')`.
- `/config/{guild_id}` — lê/atualiza `server_config`; PATCH requer admin e envia `pg_notify('fenrir_cache', 'config:{guild_id}')` para o bot recarregar sem restart.
- `/items` — CRUD de itens da loja; GET é público, POST/PATCH/DELETE requerem admin.
- `/users` — listagem paginada e consulta individual (públicas); PATCH `/users/{id}/premium` requer admin e emite `pg_notify('fenrir_cache', 'user:{id}')`.
- `/antispam/config/{guild_id}` — lê/atualiza `antispam_config` (requer admin); PATCH envia NOTIFY.
- `/antispam/audit/{guild_id}` — listagem paginada de `antispam_audit` com filtro por usuário (requer admin).
- `/antinuke/config/{guild_id}` — lê/atualiza `antinuke_config` (requer admin); PATCH envia NOTIFY.
- `/features/{guild_id}` — lista features com estado `enabled` (requer admin).
- `/features/{guild_id}/validation` — roda todos os validadores e retorna erros por feature (requer admin).
- `/features/{guild_id}/{feature}` — PUT habilita/desabilita feature; emite `pg_notify('fenrir_cache', 'feature:{guild_id}:{feature}')` (requer admin).
- `/server/{guild_id}` — GET retorna server_config + todas features com validação embutida + premium catalog (requer admin); endpoint unificado para o painel.
- `/server/{guild_id}/audit` — GET histórico paginado de alterações de config (requer admin); filtro por `kind`.
- `/config_status` slash command (admin only) — diagnóstico de configuração em embed, sem acesso direto ao DB.

Important current-state note:
- `require_admin` is applied on `antispam`, `antinuke`, `features`, `config` (PATCH), `items` (POST/PATCH/DELETE), `users` (PATCH premium), `global-config` (PATCH), and `premium` (PUT catalog) routers.
- `PATCH /users/{user_id}/premium` emits `pg_notify('fenrir_cache', 'user:{id}')` after updating the DB (Phase 6 fix).
- GET endpoints on `config`, `items`, `users`, and `premium/catalog` remain public.

**`repositories/` package** (Phases 3–6) — thin async wrappers over asyncpg for the bot's hot path:
- `repositories/items.py` — `get_all`, `get_by_id`, `create`, `delete_one`, `delete_all`
- `repositories/cooldowns.py` — `register`, `is_active`, `remaining_seconds`, `cleanup_expired`
- `repositories/users.py` — `get`, `get_or_create`, `get_all`, `add_coins`, `remove_coins`, `transfer`, `update_daily`, `update_xp_nivel`, `set_titulo`, `set_premium`, `set_dobro`, `reset_xp_one`, `reset_xp_all`, `get_ranking_coins`, `get_ranking_xp`. Utilitário `row_to_cache()` converte row DB → dict em memória (TIMESTAMPTZ → float).
- `repositories/adventures.py` — `get_all`, `get`, `upsert`, `mark_notified`, `delete`, `cleanup_expired`. Conversor `_naive_utc()` para compatibilidade com código legado.
- `repositories/guilds.py` — `build_full_data`, `sync_full_data`, `add_banco_atomic`, `sub_banco_atomic`, `get_premium_usuario`, `update_guild_name`, `remove_xp_atomic`. Implementa modelo rebuild + sync para estado transiente de guilds.

**Persistence status (per-cog):**

| Cog area | Backend |
|---|---|
| `cogs/antispam/` | ✅ Postgres (with JSON fallback) |
| `cogs/antinuke/` | ✅ Postgres for config |
| `cogs/economia/loja.py` | ✅ Postgres via `repositories/items` (with JSON fallback) |
| `cogs/economia/cooldown.py` | ✅ Postgres via `repositories/cooldowns` (with JSON fallback) |
| `cogs/economia/fenrir_coins.py` | ✅ Postgres via `repositories/users` (with JSON fallback) |
| `cogs/progressao/xp.py` | ✅ Postgres via `repositories/users` (with JSON fallback) |
| `cogs/economia/pix.py` | ✅ Postgres via `repositories/users` (with JSON fallback) |
| `cogs/progressao/aventurar.py` | ✅ Postgres via `repositories/adventures` (with JSON fallback) |
| `cogs/progressao/guild.py` | ✅ Postgres via `repositories/guilds` (with JSON fallback) |
| `cogs/progressao/guild_2.py` | ✅ Postgres via `repositories/guilds` (with JSON fallback) |

**Legacy JSON files in `data/`:**
- `data/user_data.json` — **fallback only** when `bot.db is None` (primary storage is now `users` table)
- `data/loja_data.json` — fallback only when `bot.db is None`
- `data/cooldowns_data.json` — fallback only when `bot.db is None`
- `data/antispam.json` — fallback only when `bot.db is None`
- `data/guilds_data.json` — **fallback only** (primary storage is now `guilds` + `guild_members` + `guild_invites` + `guild_alliances` + `guild_raids`)
- `data/aventuras_data.json` — **fallback only** (primary storage is now `adventures` table)

When you add new state, write directly to Postgres — do NOT add JSON files.

## Domain notes

**XP/Coins multiplier stack** (`xp.py:adicionar_xp`): Multipliers from guild level, premium plan, and the double-XP boost stack **additively** (not multiplicatively): `total = 1 + (guild−1) + (premium−1) + (dobro−1)`. Premium tiers: aventureiro=2x, lendario=4x, mitico=6x for both XP and coins. Multipliers are read from `bot.config.premium_multipliers` (JSONB) at `cog_load`.

**Shop purchase flow:** `LojaCog.comprar` → deducts coins via `FenrirCoins.remover_coins` (atomic `UPDATE users SET coins = GREATEST(0, coins - $2)` in DB mode) → delegates side effects to `CompraCog.processar_compra(posicao, user_id, item_nome, item_db_id, cooldown_secs)` → `CooldownCog.registrar_compra(user_id, item_db_id, cooldown_secs)` registra o cooldown. Em DB mode, `item_db_id` é o `id` real da tabela `items`; em JSON mode, usa o índice posicional. Se `CompraCog` estiver indisponível, `LojaCog` devolve as coins. `CooldownCog` é totalmente async — use `await` em todas as chamadas.

**Hardcoded channel/guild IDs:** Eliminated in Phase 2. All channel/guild lookups now use `bot.config.get("key")`. Never add new hardcoded IDs; add a column to `server_config` and reference via `bot.config`.

**Guard channel helper** (`main.py:FenrirBot.guard_channel`): `async def guard_channel(interaction) -> bool` — returns `True` (and replies ephemerally) if the interaction came from the wrong channel or the user isn't an admin. Use `if await self.bot.guard_channel(interaction): return` in every slash command.

**Level-up role system** (`xp.py:cargos_por_nivel`): Roles are assigned at levels 2, 5, 10, 20, 30, 40, 50. The map is now loaded from `bot.config["levelup_role_map"]` (JSONB, string keys: `{"2": role_id, ...}`) with hardcoded defaults as fallback. The `atualizar_cargos` method adds eligible roles and removes ones below the current level. Known bug — see `FIX_BUGS.md`.

**DB-mode cogs and `cog_load`:** `FenrirCoins`, `XPCog`, `PixCog`, `AventuraCog`, and guild cogs implement `async def cog_load(self)` which sets `self.use_db = self.bot.db is not None`, populates caches from the appropriate tables, and reads runtime parameters from `bot.config`. All mutation methods check `self.use_db` and call `repositories/*` functions in DB mode; `salvar_dados()` is a no-op in DB mode. Tests that instantiate these cogs must set `bot.db = None` so `cog_load` falls back to JSON mode.

**Premium activation flows** (`cogs/economia/pix.py`): There are two independent paths — do **not** mix them:
1. **Manual** (`confirmar_pagamento` button): bot-side only. Calls `atualizar_premium_usuario` (DB/JSON) → `adicionar_coins_manual` (routes through `FenrirCoins.adicionar_coins_sem_multiplo`) → `adicionar_xp_manual` (routes through `XPCog.adicionar_xp_sem_multiplo`) → adds Discord role directly. No NOTIFY sent.
2. **Automatic webhook** (`POST /webhooks/mercadopago`): API validates HMAC, fetches payment from MP, updates `users.premium` in DB, sends `pg_notify('fenrir_cache', 'premium:{user_id}:{plano}')`. Bot receives it, invalidates cache, calls `PixCog.grant_premium_rewards(user_id, plano)` which adds role + coins + XP.

**`AntiSpam.reload_config_from_db()` / `AntiNuke.reload_config_from_db()`:** Called by the bot's cache listener when it receives `antispam:{guild_id}` or `antinuke:{guild_id}` NOTIFY. Reloads the config from `antispam_config`/`antinuke_config` tables and propagates the new config object to all internal managers (`ScoreManager`, `Detector`, `Punisher`, `AuditLogger`) without requiring a bot restart.

**Copa daily summary — "no games today" is expected, not a bug** (`cogs/copa/copa.py:CopaCog._check_daily_summary`): every tick, once BRT hour hits 9 for the current date, it calls `_send_daily_summary`, which fetches `copa_svc.get_jogos_hoje()` — matches still `notstarted` inside the window from `copa_svc.janela_resumo_diario()` (fixed 24h window anchored at the 09:00 BRT checkpoint, not calendar-day). On a rest day between rounds this list is legitimately empty, and `_send_daily_summary` sends a "sem jogos hoje" embed + current bracket image (`_send_no_games_today`) instead of the games/bracket/artilharia summary — silently, with no exception logged. Don't mistake a quiet morning for a broken monitor tick; check `get_jogos_rodada()`/`get_jogos_hoje()` for the actual calendar before assuming a bug. The end-of-day bracket+artilharia post (previously sent ~1h after the last game of a day finished) was removed — the only automatic bracket sends now are the 09:00 daily summary (games or no-games variant).

**Tests:** Use `pytest-asyncio` with `asyncio_mode = auto`. Pattern for testing cogs: mock `commands.Bot`, set `bot.db = None` and `cog.use_db = False` to keep tests in JSON mode, patch background `tasks.loop` decorators to prevent them from starting, and use `AsyncMock` for Discord interactions. Test fixtures must populate `bot.config` (a `ServerConfig` wrapping a dict with at least `commands_channel_id`) so that `guard_channel` can resolve correctly.

## Migration plan

A full migration plan with the status of every phase lives in `MIGRATION.md`. Phases 0–6 are complete.

Key invariants for any new code:
- **Bot talks directly to Postgres via `asyncpg`** — no HTTP intermediary between bot and database.
- **`server_config` is the source of truth for IDs and parameters** — never add new hardcoded IDs; add a column and reference via `bot.config`.
- **`antispam_config` and `antinuke_config` are JSONB** — change `AntispamConfig`/`AntinukeConfig` dataclasses freely; `from_dict()` is tolerant to missing/extra fields.
- **`FenrirCoins` + `XPCog` race condition is fixed** — mutations use targeted `UPDATE … SET field = $2` (not write-entire-row), so concurrent saves from the two cogs never overwrite each other.
- **Resilience contract**: if `bot.db is None`, the bot logs a warning and continues in JSON mode. Code paths that touch the DB must check `self.use_db` (cogs) or `if self.bot.db is not None` (elsewhere).
- **New state goes to Postgres** — do NOT add JSON files. If a cog needs a new persistent field, add a column to the appropriate table and expose it through `repositories/`. Guild and adventure data are now Postgres-backed; all cogs use dual-mode DB/JSON with `self.use_db` and `cog_load()` pattern.
- **Cache invalidation is cross-process via NOTIFY** — when the API updates any shared state (premium, server_config, antispam/antinuke config), it must call `pg_notify('fenrir_cache', '<kind>:<id>')`. The bot's listener handles the rest. Never rely on TTL expiry alone for admin operations.
- **NOTIFY contract is complete (Phase 6):** `PATCH /config` emits `config:`, `PATCH /users/{id}/premium` emits `user:`, `PUT /features/{guild_id}/{feature}` emits `feature:`. All mutating endpoints on config/users/items/features use `Depends(require_admin)`.
- **API auth**: new endpoints that mutate config must use `Depends(require_admin)` from `api/routers/auth.py`. The dependency is a no-op in dev mode (JWT_SECRET at default value); set a real secret in production via `JWT_SECRET` env var.

## Phase 6 details: Guilds + Adventures

**Guild data model** (`repositories/guilds.py`):
- Guilds use a **rebuild + sync** pattern: `build_full_data()` reconstructs the full `guilds_data.json` shape from normalized DB tables; `sync_full_data()` upserts all records in a single transaction.
- `guilds` table stores core state (name, leader, bank, level, XP, motto, emoji, timestamps).
- `guild_members` stores membership with role (`Líder`/`Admin`/`Membro`) and join time.
- `guild_invites` stores pending invites with creator and expiration (UNIX timestamp in seconds).
- `guild_alliances` stores bilateral alliances (both A→B and B→A stored for O(1) lookup).
- `guild_raids` stores active raids as transient JSONB state—allows raid shape to evolve without schema migrations.
- Atomic operations: `add_banco_atomic()`, `sub_banco_atomic()` (with balance guard), `remove_xp_atomic()` prevent overflow/underflow.

**Adventure data model** (`repositories/adventures.py`):
- `adventures` table has one row per active user. Field `inicio` is TIMESTAMPTZ (UTC); field `situacao` is JSONB (adventure type/name/description/image).
- `_naive_utc()` converter returns `datetime` objects without tzinfo (naive UTC) for compatibility with legacy code in `aventurar.py`.
- Unique constraint on `user_id` ensures at most one adventure per player.
- `cleanup_expired()` removes completed adventures older than N hours (default 24).

**Cog patterns** (`cogs/progressao/aventurar.py`, `guild.py`, `guild_2.py`):
- All three cogs implement `async def cog_load(self)` → sets `self.use_db` and initializes memory caches from the DB.
- In DB mode, `salvar_dados()` becomes a background async task (`asyncio.create_task()`) that calls `sync_full_data()` or appropriate `upsert()` functions—never blocks the bot.
- Reads are always async: `obter_aventura_usuario()`, etc. check `self.use_db` and call `repositories/*` functions; fallback to JSON load on error.
- Time calculations (`obter_tempo_restante()`, `aventura_expirada()`, etc.) work on in-memory `datetime` objects; no DB round-trip needed.

**JSON fallback guarantee:**
- If `bot.db is None` at startup, `cog_load()` skips DB init and cogs operate entirely from JSON files.
- Imports in `db/migrate.py` (`_import_guilds()`, `_import_adventures()`) run on startup if tables are empty, populating the DB from `data/*.json`.
- Error handling in import is granular (per-record); one malformed invite doesn't prevent guild import.
