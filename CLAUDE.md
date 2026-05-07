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

The existing test suite has many pre-existing failures unrelated to the database migration (`pytest-asyncio` config + `discord.py` mock incompatibilities). When changing code, ensure your edits don't *add* failures, but don't expect a green run.

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `TOKEN` — Discord bot token
- `ACCESS_TOKEN` — Mercado Pago access token
- `POSTGRES_PASSWORD` — Postgres password
- `DATABASE_URL` — connection string. In docker-compose the host is `postgres`; for `python main.py` against a locally-exposed Postgres, use `localhost:5432`.

The bot **does not crash if Postgres is unavailable** — it logs a warning and operates in legacy-JSON mode. This compatibility window will close after Phase 4.

## Architecture

**Entry point:** `main.py` creates a `FenrirBot(commands.Bot)` with prefix `!` and all intents. On `setup_hook` it:
1. Calls `_init_database()` — initializes `bot.db` (asyncpg pool), applies migrations from `db/migrations/*.sql`, imports legacy JSONs into the DB if the target tables are empty, and loads `bot.config` (a `ServerConfig` cached for 5 min).
2. Walks `cogs/` and loads extensions. **The walker has special handling for cog-packages**: if a directory has `__init__.py` defining `setup()` (e.g. `cogs/antispam`, `cogs/antinuke`), it's loaded once as a package and submodules are *not* loaded as separate cogs. Directories with empty `__init__.py` (e.g. `cogs/economia/`) keep the old behavior — each `.py` is its own cog.
3. Syncs slash commands with `tree.sync()`.

On `on_ready`, it posts/refreshes persistent embeds in fixed channels (status, colors, pix plans, tickets) — these channel IDs are still hardcoded; Phase 2 moves them to `bot.config`.

**Cog system:** Each entry-point module (file or package with `setup()` in `__init__.py`) defines `async def setup(bot)`. Cogs communicate with each other via `bot.get_cog("CogName")` — always check for `None`. Cogs that need the database access `bot.db` (the asyncpg pool) and `bot.config` (the cached `ServerConfig`); both can be `None` in degraded mode.

**Branches (post-unification):**
- **`main`** — unified bot: economy, XP, guilds, shop, Mercado Pago, Riot/Steam/GNews APIs **plus** antinuke, antispam, invite blocker, auto-remove bots. **25 cogs** total (4 of them brought from `fenrir_security` in Phase 1).
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

**`api/` package** — FastAPI scaffold (Phase 0). `/health` checks the DB; `/config/{guild_id}` reads the row. Auth, panel, and Mercado Pago webhook are scheduled for Phase 5.

**Persistence status (per-cog):**

| Cog area | Backend |
|---|---|
| `cogs/antispam/` | ✅ Postgres (with JSON fallback) |
| `cogs/antinuke/` | ✅ Postgres for config |
| Everything else (XP, coins, shop, cooldowns, guilds, adventures) | Still JSON |

**Legacy JSON files in `data/`** (still in use by JSON-backed cogs):
- `data/user_data.json` — XP, level, title, premium plan, coins, daily streak per user (Phase 4 target)
- `data/guilds_data.json` — guild membership and stats (Phase 6 target)
- `data/loja_data.json` — shop items, sorted by price descending (Phase 3 target)
- `data/aventuras_data.json` — in-progress adventures per user (Phase 6 target)
- `data/cooldowns_data.json` — per-user, per-item cooldown timestamps (Phase 3 target)
- `data/antispam.json` — only used as fallback when `bot.db is None`

When you add new state, write directly to Postgres — do NOT add JSON files.

## Domain notes

**XP/Coins multiplier stack** (`xp.py:adicionar_xp`): Multipliers from guild level, premium plan, and the double-XP boost stack **additively** (not multiplicatively): `total = 1 + (guild−1) + (premium−1) + (dobro−1)`. Premium tiers: aventureiro=2x, lendario=4x, mitico=6x for both XP and coins. After Phase 2, multipliers come from `bot.config.premium_multipliers` (JSONB).

**Shop purchase flow:** `LojaCog.comprar` → deducts coins via `FenrirCoins.remover_coins` → delegates side effects to `CompraCog.processar_compra` → `CooldownCog.registrar_compra` records the per-item cooldown. If `CompraCog` is unavailable, `LojaCog` refunds the coins.

**Hardcoded channel/guild IDs:** Eliminated in Phase 2. All channel/guild lookups now use `bot.config.get("key")`. Never add new hardcoded IDs; add a column to `server_config` and reference via `bot.config`.

**Guard channel helper** (`main.py:FenrirBot.guard_channel`): `async def guard_channel(interaction) -> bool` — returns `True` (and replies ephemerally) if the interaction came from the wrong channel or the user isn't an admin. Use `if await self.bot.guard_channel(interaction): return` in every slash command.

**Level-up role system** (`xp.py:cargos_por_nivel`): Roles are assigned at levels 2, 5, 10, 20, 30, 40, 50. The map is now loaded from `bot.config["levelup_role_map"]` (JSONB, string keys: `{"2": role_id, ...}`) with hardcoded defaults as fallback. The `atualizar_cargos` method adds eligible roles and removes ones below the current level. Known bug — see `FIX_BUGS.md`.

**Tests:** Use `pytest-asyncio` with `asyncio_mode = auto`. Pattern for testing cogs: mock `commands.Bot`, patch background `tasks.loop` decorators to prevent them from starting, and use `AsyncMock` for Discord interactions. Test fixtures must populate `bot.config` (a `ServerConfig` wrapping a dict with at least `commands_channel_id`) so that `guard_channel` can resolve correctly.

## Migration plan

A full migration plan with the status of every phase lives in `MIGRATION.md`. Phases 0, 1, and 2 are done; Phase 3 (loja + cooldowns no DB) is next.

Key invariants for any new code:
- **Bot talks directly to Postgres via `asyncpg`** — no HTTP intermediary between bot and database.
- **`server_config` is the source of truth for IDs and parameters** — never add new hardcoded IDs; add a column and reference via `bot.config`.
- **`antispam_config` and `antinuke_config` are JSONB** — change `AntispamConfig`/`AntinukeConfig` dataclasses freely; `from_dict()` is tolerant to missing/extra fields.
- **`FenrirCoins` + `XPCog` race condition** on `user_data.json` will be resolved with atomic `UPDATE ... RETURNING` once on Postgres (Phase 4).
- **Resilience contract**: if `bot.db is None`, the bot logs a warning and continues. Code paths that touch the DB must check `if self.bot.db is not None`.
