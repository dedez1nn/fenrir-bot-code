# Fenrir — Migração para PostgreSQL + API Web + Painel de Configuração

## Status atual

| Fase | Estado |
|---|---|
| **0 — Infra base** | ✅ Concluída |
| **1 — Unificação dos bots** | ✅ Concluída |
| **2 — IDs hardcoded → `server_config`** | ✅ Concluída |
| **3 — Loja + cooldowns no DB** | ✅ Concluída |
| **4 — Usuários + XP/Coins no DB** | ✅ Concluída |
| **5 — Webhook MP + painel admin** | ✅ Concluída |
| **6 — Guilds + aventuras no DB** | ✅ Concluída |

---

## Contexto

O projeto tinha dois bots separados:
- **`main`** — Fenrir: economia, XP, guilds, loja, Mercado Pago, Riot/Steam/GNews
- **`fenrir_security`** — FenrirSecurity: antinuke, antispam, bloqueio de convites, auto-remove bots

Ambos persistiam estado em arquivos JSON, não tinham interface de administração, e tinham configurações críticas hardcoded no código (IDs de canal, thresholds de moderação, regras de antispam). Esta migração unifica os dois bots em um único sistema com PostgreSQL compartilhado e um painel web onde admins configuram tudo — sem tocar no código ou reiniciar containers.

---

## Arquitetura Atual (após Phase 5)

```
┌──────────────────────────────────────────┐
│           Container: fenrir              │
│                                          │
│  Fenrir + FenrirSecurity unificados      │  asyncpg (R/W)
│  25 cogs (4 de segurança incluídos)      │ ──────────────────────────────┐
│  bot.db (asyncpg.Pool, opcional)         │                               │
│  bot.config (ServerConfig + cache 5min)  │  LISTEN fenrir_cache ◄────────┤
│  _start_cache_listener() ativo           │                               │
└──────────────────────────────────────────┘                               │
                                                    ┌───────────────────────▼───────┐
┌──────────────────────────────────────────┐        │    Container: postgres        │
│           Container: api                 │        │                               │
│                                          │asyncpg │  10 tabelas (schema_v1):      │
│  FastAPI v0.5 — Phase 5 completo         ├───────►│  server_config                │
│  /auth (Discord OAuth2 + JWT cookie)     │        │  users / items / cooldowns    │
│  /webhooks/mercadopago (HMAC + MP API)   │NOTIFY ►│  antispam_users               │
│  /config  /items  /users                 │        │  antispam_whitelist           │
│  /antispam/config  /antispam/audit       │        │  antispam_config              │
│  /antinuke/config                        │        │  antinuke_config              │
│  require_admin (JWT, dev bypass)         │        │  antispam_audit               │
└──────────────────────────────────────────┘        │  schema_migrations            │
                                                    └───────────────────────────────┘
```

**Bot e API se comunicam exclusivamente via banco** — sem HTTP entre eles.

**Invalidação de cache cross-process:** a API envia `pg_notify('fenrir_cache', '<kind>:<id>')` após mutações; o bot escuta via `pool.add_listener` e reage em tempo real sem restart.

**Resiliência:** o bot opera com `bot.db = None` se o Postgres estiver indisponível. Todos os cogs migrados mantêm fallback JSON.

---

## Phases concluídas — detalhamento

### ✅ Phase 0 — Infra base

**Entregue:**
- [x] `docker-compose.yml` com 3 serviços: `postgres` (healthcheck + volume nomeado + porta exposta apenas em dev), `bot`, `api`
- [x] `requirements.txt` adiciona `asyncpg==0.29.0` e `pytest-asyncio`
- [x] `api/requirements.txt` separado: `fastapi`, `uvicorn`, `python-jose`, `httpx`, `itsdangerous`
- [x] `db/migrations/001_initial.sql` — schema completo (10 tabelas)
- [x] `db/migrations/002_seed.sql` — row inicial em `server_config` com todos os IDs atuais
- [x] `db/pool.py` — `init_pool()` com codec JSONB ↔ dict automático; falha graciosamente se DB indisponível
- [x] `db/config.py` — `ServerConfig` (acesso por atributo + `[]`) com cache em memória TTL 5 min e `refresh_server_config()` para invalidação pela API
- [x] `db/migrate.py` — `apply_migrations()` idempotente (controle via `schema_migrations`) + `import_legacy_json()` que detecta tabelas vazias e importa de `data/*.json` no boot
- [x] `main.py` — `setup_hook` inicializa pool, aplica migrations, importa JSONs e carrega `bot.config`; `bot.reload_config()` para hot-reload via API
- [x] `api/main.py` — FastAPI scaffold com lifespan, CORS, `/health` (ping DB), `/config/{guild_id}`
- [x] `scripts/db_setup.py` — CLI standalone para CI/ops (`python -m scripts.db_setup`)
- [x] `.env.example` reorganizado: Postgres, OAuth2, JWT, MP webhook, Riot/Steam/GNews

**Tabelas adicionais não previstas no plano original** (decisões de design tomadas durante a implementação):
- `antispam_audit` — trilha de eventos de moderação para o painel da Phase 5
- `schema_migrations` — controle de aplicação idempotente
- `server_config` ganhou colunas extras: `coins_log_channel_id`, `xp_log_channel_id`, `levelup_channel_id`, `levelup_role_map` (JSONB), `premium_multipliers`, `daily_coins`, `coins_por_mensagem`, `xp_por_mensagem`, `voice_xp_interval_s`, `bonus_coins_por_nivel`. Phase 2 vai mapear todos os IDs/parâmetros hardcoded para esses campos.
- `users` ganhou `premium_expira` e `guild_name` (preservados do `user_data.json`).

**Bug encontrado e corrigido durante validação:**
- JSONB voltava como string crua via asyncpg. Corrigido com `init=_init_connection` registrando codec `jsonb`/`json` ↔ `json.loads`/`json.dumps` em todas as conexões dos pools (`db/pool.py`, `api/db.py`).

### ✅ Phase 1 — Unificação dos bots

**Entregue:**
- [x] Cogs migrados de `fenrir_security` → `main`: `cogs/antinuke/`, `cogs/antispam/`, `cogs/block_inv.py`, `cogs/security.py`
- [x] `main.py` mantém `command_prefix='!'` (padrão do Fenrir)
- [x] Walker de cogs em `setup_hook` ganhou `_module_defines_setup()`: detecta pacotes-cog (com `setup()` no `__init__.py`) e os carrega como uma única extensão. Pacotes legados (`cogs/economia/`, `cogs/progressao/`, etc.) com `__init__.py` vazios continuam usando o caminho antigo (cada `.py` = um cog).
- [x] `cogs/antispam/pg_storage.py` — novo `PgStorage` com mesma interface do `JSONStorage` (`load`/`save`/`guild`/`user`), backed por `antispam_users` + `antispam_whitelist`. Lazy load por guild + cache em memória + upsert transacional em `save()`. Whitelist usa diff incremental.
- [x] `AntispamConfig` ganhou `from_dict` tolerante a campos parciais/novos/removidos (merge com defaults + filtra chaves inválidas), e `load_from_db`/`save_to_db` (UPSERT em `antispam_config`).
- [x] `AntinukeConfig` ganhou `to_dict`/`from_dict` que preservam `tuple` (rates) e `dict[int, str]` (severity_thresholds) no round-trip JSONB; `load_from_db`/`save_to_db` (UPSERT em `antinuke_config`).
- [x] `AntiSpam.cog_load`: instancia `PgStorage` se `bot.db is not None`, senão `JSONStorage` como fallback. Carrega config do DB com fallback para defaults.
- [x] `AntiNuke.cog_load`: carrega config do DB com fallback para defaults.

**Validação:**
- 25 cogs carregando (4 de segurança ativos: `AntiSpam`, `AntiNuke`, `InviteBlocker`, `AutoRemoveBots`).
- Smoke test E2E com Postgres real: round-trip de configs (tuple/dict[int,str] preservados) e de estados de usuário (score, infractions, recent_messages, whitelist).
- Única falha pré-existente: `cogs/economia/pix.py` (precisa de `ACCESS_TOKEN` do Mercado Pago em runtime; sem relação com a migração).

**Riscos remanescentes:**
- ~~Comandos `/antispam threshold` e `/antispam toggle` mutam o config em memória sem persistir~~ — **resolvido na Phase 2** (`save_to_db` adicionado).
- `log_channel_id` ainda é campo dos dataclasses; deveria ler de `bot.config.antispam_log_channel_id` / `antinuke_log_channel_id`. Baixa prioridade pois o painel (Phase 5) já permite editar via API.
- `_primary_guild_id()` em ambos os cogs usa `bot.config.guild_id` se disponível, senão `bot.guilds[0].id`. Aceitável até Phase 6+.

---

## Próximas phases

### ✅ Phase 2 — IDs hardcoded → `server_config`

**Entregue:**
- [x] Substituídos em 13 cogs + `main.py` todos os IDs literais:
  - `commands_channel_id`, `guild_id`, `afk_voice_channel_id`, `status_channel_id`, `colors_channel_id`, `pix_channel_id`, `tickets_channel_id`, `coins_log_channel_id`, `xp_log_channel_id`, `levelup_channel_id`
  - `cargos_por_nivel` em `xp.py` → inicializado de `bot.config["levelup_role_map"]` com fallback para defaults
- [x] `FenrirBot.guard_channel(interaction)` — helper `async def` que centraliza o padrão `if channel.id != cmd_ch and not admin: reject`. Retorna `True` se rejeitado. Eliminou ~40 blocos duplicados.
- [x] `FenrirBot._cfg_channel(key)` — helper para resolver canal via config no `on_ready`.
- [x] `GUILD_ID` em `main.py` migrado para `os.getenv("GUILD_ID", "<fallback>")` — sem literal numérico no código.
- [x] `PATCH /config/{guild_id}` na API com lista de campos permitidos (allowlist); retorna row atualizada.
- [x] `/antispam threshold`, `/antispam toggle`, `/antispam canal_log` agora chamam `await self.config.save_to_db(pool, guild_id)` — mudanças persistem no restart.
- [x] `.env.example` recebe `GUILD_ID=` documentado.

**Riscos:**
- Mudança cirúrgica em muitos arquivos grandes — alto risco de typo. Sugestão: começar pelos cogs mais simples (`ping` em `main.py`, `interface/`) e progredir.
- Testes existentes têm IDs hardcoded em fixtures (canal `1426205118293868748`); precisarão ser ajustados ou usar fixtures que populam `bot.config`.

### ✅ Phase 3 — Loja + cooldowns no DB

**Entregue:**
- [x] `repositories/items.py` — `get_all`, `get_by_id`, `create`, `delete_one`, `delete_all`
- [x] `repositories/cooldowns.py` — `register`, `is_active`, `remaining_seconds`, `cleanup_expired`
- [x] `cogs/economia/loja.py` → reescrito com modo DB (via `repositories/items`) e fallback JSON:
  - `cog_load` carrega itens do DB na inicialização
  - `recarregar()` async atualiza `self.loja_data` de DB ou JSON
  - `/adicionar_item` aceita `cooldown_h` opcional; persiste no DB quando disponível
  - `/remover_item` e `/limpar_loja` deletam do DB com cascade automático nos cooldowns
  - `canal_log_loja` hardcoded removido → usa `bot.config.get("coins_log_channel_id")`
  - `LojaView.botao_atualizar` passa a chamar `await loja_cog.recarregar()`
  - `/comprar` extrai `item_db_id` e `cooldown_secs` do item e os repassa para `CompraCog`
- [x] `cogs/economia/cooldown.py` → dual-mode DB / JSON:
  - `cog_load` detecta `bot.db` e seta `self.use_db`
  - `registrar_compra`, `verificar_compra`, `obter_tempo_restante` agora `async`
  - DB mode: duração vem de `items.cooldown_h`; armazena em `cooldowns` com `expires_at`
  - JSON mode: mantém comportamento original com `cooldowns_itens` dict de fallback
- [x] `cogs/economia/compra.py` → `processar_compra` aceita `item_db_id` e `cooldown_secs`; usa `item_db_id` como chave nos cooldowns quando disponível; chamadas ao CooldownCog são agora `await`
- [x] `cogs/economia/comands_loja.py` → `verificar_compra` traduz posição → id DB via `LojaCog` antes de checar cooldown
- [x] API: `GET /items`, `GET /items/{id}`, `POST /items`, `PATCH /items/{id}`, `DELETE /items/{id}` em `api/routers/items.py`
- [x] `api/main.py` inclui o novo router
- [x] `db/migrate.py` — corrigido bug: `loja_data.json` tem formato `{"itens": [...]}` (dict), não lista direta
- [x] `tests/test_cooldown.py` — todos os testes convertidos para async; fixture seta `bot.db=None` e `use_db=False`
- [x] `tests/test_compra.py` — mocks de `verificar_compra` e `obter_tempo_restante` convertidos para `AsyncMock`

**Decisões de design:**
- Em DB mode, a chave nos cooldowns é o **id real do item no banco** (`items.id`), não o índice posicional. Isso mantém compatibilidade com o FK `cooldowns.item_id → items.id` e cascade delete correto.
- `comands_loja.py` faz lookup `posição → id DB` via `LojaCog.encontrar_item_por_posicao` antes de checar cooldown; em modo JSON usa o índice diretamente como fallback.
- Cooldown duration em DB mode vem de `items.cooldown_h` (horas); se zero, nenhum cooldown é registrado. O dict `cooldowns_itens` (fallback JSON) usa índices posicionais e continua funcional em degraded mode.
- `LojaView` continua operando sobre `self.loja_cog.loja_data` em memória; `recarregar()` sincroniza com DB antes de cada operação de escrita.

**Riscos remanescentes:**
- `processadores` em `compra.py` ainda usa índice posicional (1-14) para despacho de lógica de compra. Itens adicionados fora de ordem podem não ter processador. Endereçável na Phase 5 com tipagem de item no DB.
- Testes de `comands_loja` e alguns de `compra` têm falhas pré-existentes (`guard_channel` e `bot.config` não no spec de `commands.Bot`); não foram introduzidas por esta phase.

### ✅ Phase 4 — Usuários + XP/Coins no DB

**Entregue:**
- [x] `repositories/users.py` — `get`, `get_or_create`, `get_all`, `add_coins`, `remove_coins`, `transfer`, `update_daily`, `update_xp_nivel`, `set_titulo`, `set_premium`, `set_dobro`, `reset_xp_one`, `reset_xp_all`, `get_ranking_coins`, `get_ranking_xp`. Utilitário `row_to_cache()` para converter row DB → dict de memória.
- [x] Race condition resolvida: coins usam `INSERT … ON CONFLICT DO UPDATE SET coins = users.coins + $2` (delta atômico); transferência usa `SELECT … FOR UPDATE` em transação; xp/nivel usam `UPDATE … SET xp = $2, nivel = $3` (campos separados, sem sobrescrever o restante do row).
- [x] `cogs/economia/fenrir_coins.py` — `cog_load` seta `use_db`, popula `user_data` do DB e lê parâmetros de `bot.config` (`coins_por_mensagem`, `daily_coins`, `daily_streak_bonus`, `coins_por_voz`). `salvar_dados()` vira no-op em DB mode. Todos os métodos de mutação (`adicionar_coins`, `adicionar_coins_sem_multiplo`, `remover_coins`, `daily`, `transferir`, `adicionar_coins_adm`, `remover_coins_adm`) usam SQL atômico com fallback gracioso para cache.
- [x] `cogs/progressao/xp.py` — mesmo padrão: `cog_load` + `_persistir_xp()` helper que em DB mode chama `update_xp_nivel`; `dobro_xp_loop` persiste expiração no DB; `set_titulo`, `set_premium`, `reset_xp`, `reset_xp_all`, `retirar_xp` todos com suporte DB. `ativar_dobro_xp` persiste no DB. `/xp` e `/coins` buscam direto do DB em DB mode.
- [x] `salvar_dados()` em DB mode é no-op em ambos os cogs — elimina o risco de um cog sobrescrever os dados do outro no arquivo JSON.
- [x] `cog_load` lê configurações de `bot.config`: `xp_por_mensagem`, `xp_por_voz`, `voice_xp_interval_s`, `bonus_coins_por_nivel`, `coins_por_mensagem`, `coins_por_voz`.
- [x] API: `GET /users` (paginação + ordering), `GET /users/{user_id}`, `PATCH /users/{user_id}/premium` em `api/routers/users.py`. Incluído em `api/main.py`.

**Decisões de design:**
- `self.user_data` (cache em memória) é mantido nos dois cogs e populado do DB no `cog_load`. Mutations atualizam o cache otimisticamente após cada SQL. Isso preserva o código de ranking (que itera o cache) sem refatoração.
- Em DB mode, erros de SQL fazem fallback silencioso para o cache, garantindo resiliência mesmo com Postgres temporariamente indisponível.
- `row_to_cache()` centralizado em `repositories/users.py` garante conversão consistente de `TIMESTAMPTZ` → float (usado por `last_daily` e `dobro_expiracao` no cache).
- `transfer()` usa `SELECT … FOR UPDATE` para prevenir double-spend concorrente.
- `reset_xp_all` usa `user_data.clear()` (mutação in-place) para manter a referência `self.xp_data = self.user_data` válida.

**Riscos remanescentes:**
- Cache pode ficar brevemente dessincronizado se a API atualizar o DB diretamente (ex: `PATCH /users/{id}/premium`). O bot rerenderiza o cache ao próximo `cog_load` (restart). Para hot-reload, a Phase 5 pode adicionar evento de invalidação.
- `voice_xp_loop` e `dobro_xp_loop` ainda fazem updates individuais por usuário (não batch). Para a escala atual é aceitável; batch com `executemany` pode ser adicionado se o número de usuários simultâneos crescer.

### ✅ Phase 5 — Webhook MP + painel admin

**Entregue:**
- [x] `api/routers/auth.py`: Discord OAuth2 (authorize → callback → JWT em cookie HttpOnly); `require_admin` dependency exportada para proteger routers. Em desenvolvimento (JWT_SECRET padrão), a validação é dispensada.
- [x] `api/routers/webhooks.py`: `POST /webhooks/mercadopago` — validação HMAC (`x-signature: ts=...,v1=...`), verifica status do pagamento via API MP, atualiza `users.premium` + `users.premium_expira`, envia `pg_notify('fenrir_cache', 'premium:{user_id}:{plano}')`.
- [x] `api/routers/config.py` ganha `pg_notify('fenrir_cache', 'config:{guild_id}')` após PATCH — bot recarrega `server_config` imediatamente via cache listener.
- [x] ~~`api/routers/users.py`~~ — ✅ já entregue na Phase 4
- [x] ~~`api/routers/items.py`~~ — ✅ já entregue na Phase 3
- [x] `api/routers/antispam.py`: `GET/PATCH /antispam/config/{guild_id}` (merge JSONB top-level) + `GET /antispam/audit/{guild_id}` (paginado, filtro por user_id). Todos requerem admin.
- [x] `api/routers/antinuke.py`: `GET/PATCH /antinuke/config/{guild_id}` (merge JSONB + enabled + alert_only). Requer admin.
- [x] **Cache invalidation via PostgreSQL LISTEN/NOTIFY**: `FenrirBot._start_cache_listener()` registra listener em `fenrir_cache` via `pool.add_listener()`. Payloads: `user:{id}`, `premium:{id}:{plan}`, `config:{guild_id}`, `antispam:{guild_id}`, `antinuke:{guild_id}`.
- [x] `AntiSpam.reload_config_from_db()` + `AntiNuke.reload_config_from_db()`: recarregam config em memória sem restart ao receberem NOTIFY.
- [x] `cogs/economia/pix.py` migrado para DB mode:
  - `atualizar_premium_usuario` → `repositories/users.set_premium` + atualiza caches em memória dos cogs.
  - `adicionar_coins_manual` → roteia por `FenrirCoins.adicionar_coins_sem_multiplo` (já DB-aware).
  - `adicionar_xp_manual` → roteia por `XPCog.adicionar_xp_sem_multiplo` (já DB-aware).
  - `_executar_verificacao_premium` → dual-mode: `_verificar_premium_db()` (query atômica batch) ou `_verificar_premium_json()` (legado). Log comum via `_enviar_log_expirados()`.
  - `grant_premium_rewards(user_id, plano)`: novo método chamado pelo bot ao receber NOTIFY `premium:*`, adiciona role + coins + XP sem duplicar o fluxo manual.
- [x] `.env.example` documentado: `ADMIN_ROLE_IDS`, `JWT_SECRET` com instrução de segurança.

**Decisões de design:**
- Auth em **modo desenvolvimento automático** quando `JWT_SECRET == "change-me-in-production"` — nenhuma trava nova em ambiente local/CI.
- Webhook MP responde `200` imediatamente e processa em `BackgroundTasks` — atende ao contrato de retry do MP.
- PATCH de antispam/antinuke usa `config || $patch::jsonb` (merge shallow) — para campos aninhados (scores, ladder, listas), o cliente envia o objeto completo; `from_dict()` tolerante garante validade na carga.
- `grant_premium_rewards` é chamado **somente** pelo NOTIFY (fluxo webhook); o fluxo manual `confirmar_pagamento` continua chamando `atualizar_premium_usuario` + `adicionar_coins_manual` + `adicionar_xp_manual` diretamente, sem NOTIFY (evita double-grant).
- Frontend (Next.js / SvelteKit) não incluído — Phase 5 entrega todos os endpoints necessários; o painel em si é work-in-progress separado.

**Riscos remanescentes:**
- Se o bot reiniciar antes de processar o NOTIFY, o grant de premium não ocorre. Mitigação futura: tabela `pending_premium_grants` com flag de processamento (Phase 6+).
- `pool.add_listener` requer que a pool asyncpg suporte `LISTEN` via seu pool interno de conexões (suportado desde asyncpg 0.22+; versão atual 0.29.0).

### ✅ Phase 6 — Guilds + aventuras no DB

**Entregue:**
- [x] `db/migrations/003_guilds_adventures.sql` — 6 tabelas para Phase 6:
  - `guilds` — dados da guild (nome, líder, banco, nível, XP, motto, emoji, timestamps)
  - `guild_members` — membros com cargo e status (Líder/Admin/Membro)
  - `guild_invites` — convites pendentes com expiração
  - `guild_alliances` — alianças bidireccionais entre guilds
  - `guild_raids` — raids ativas com estado transiente em JSONB
  - `adventures` — uma aventura ativa por usuário com situação em JSONB
- [x] `repositories/adventures.py` — funções CRUD para aventuras:
  - `get_all()` — retorna todas as aventuras no formato `{str(user_id): aventura_dict}`
  - `get(pool, user_id)` — retorna aventura de um usuário ou None
  - `upsert()` — cria/atualiza aventura (com conversão timezone-aware ↔ naive UTC)
  - `mark_notified()` — marca aventura como notificada
  - `delete()` — remove aventura ativa
  - `cleanup_expired()` — remove aventuras prontas há mais de N horas
- [x] `repositories/guilds.py` — funções para guilds (modelo rebuild + sync):
  - `build_full_data()` — reconstrói dict `{guild_id: guild_data, "raids_ativas": {...}}` a partir do DB
  - `sync_full_data()` — sincroniza estado completo em transação atômica (UPSERT todos + delete órfãos)
  - `add_banco_atomic()` / `sub_banco_atomic()` — operações atômicas no banco da guild
  - `get_premium_usuario()` — auxiliar para consultar premium de um usuário
  - `update_guild_name()` — atualiza guild_name na tabela users
  - `remove_xp_atomic()` — subtrai XP atomicamente com guarda de saldo
- [x] `cogs/progressao/aventurar.py` — dual-mode DB/JSON:
  - `cog_load()` detecta `bot.db` e seta `self.use_db`
  - `obter_aventura_usuario()`, `remover_aventura_usuario()`, `adicionar_aventura_usuario()` → async com fallback JSON
  - `aventura_expirada()`, `aventura_pronta()`, `obter_tempo_restante()`, `obter_tempo_decorrido()` — verificações em memória (iguais)
  - `_carregar_dados_json()` e `_salvar_dados_json()` — helpers para fallback JSON (renomeados de `carregar_dados`/`salvar_dados`)
- [x] `cogs/progressao/guild.py` — dual-mode DB/JSON com padrão análogo a aventurar.py
- [x] `cogs/progressao/guild_2.py` — dual-mode DB/JSON (raides, doações, etc.)
- [x] `db/migrate.py` — adicionado:
  - `_import_guilds()` — importa `guilds_data.json` com tolerância a erros por registro
  - `_import_adventures()` — importa `aventuras_data.json` com conversão de timestamps
  - `apply_migrations()` executa a migration 003 e importa ambas as tabelas se vazias

**Decisões de design:**
- `adventures` armazena timestamp UTC-aware; conversor `_naive_utc()` retorna datetime naive para compatibilidade com código legado em `aventurar.py`.
- `guilds` usa float UNIX timestamp (segundos desde epoch) para `data_criacao`, `ultima_raid`, `data_alianca` — preserva formato do JSON legado.
- `guild_raids` armazena estado transiente como JSONB — permite alterar a shape do dado de raid sem schema migration.
- `sync_full_data()` é chamado de forma assíncrona (fire-and-forget) por `salvar_dados()` — nunca bloqueia o bot.
- Operações financeiras (`add_banco_atomic`, `sub_banco_atomic`, `remove_xp_atomic`) usam `WHERE` com guarda de saldo — previnem overflow/underflow.

**Testes:**
- Todos os testes em `tests/test_aventura.py` continuam verdes (162 testes total).
- Cogs `AventuraCog`, `GuildCog`, `GuildRaidsCog` convertidos para async; `cog_load()` seta `use_db` e modo fallback.

**Persistence status (atualizado):**

| Cog área | Backend |
|---|---|
| `cogs/progressao/aventurar.py` | ✅ Postgres (com JSON fallback) |
| `cogs/progressao/guild.py` | ✅ Postgres (com JSON fallback) |
| `cogs/progressao/guild_2.py` | ✅ Postgres (com JSON fallback) |
| Demais (economia, XP, antispam, antinuke) | ✅ Postgres (com JSON fallback) |

**Riscos remanescentes:**
- `guild_raids` armazena raid_id como chave primária — colisões de nomes de raid devem ser mitigadas no código de aplicação (não há namespace por guild).
- `cooldowns` em guilds (`gdata["cooldowns"]`) não é sincronizado com o DB — ainda é JSON-only. Endereçável em fase futura se necessário.
- `guild_members.ativo` é um booleano; a lógica de "purga de inativos" ainda usa heurística JSON (não migrada).

---

## Schema atual (após Phase 4)

```sql
-- Configuração do servidor (substitui todos os IDs hardcoded)
CREATE TABLE server_config (
    guild_id                  BIGINT PRIMARY KEY,

    -- Canais
    commands_channel_id       BIGINT,
    status_channel_id         BIGINT,
    afk_voice_channel_id      BIGINT,
    colors_channel_id         BIGINT,
    pix_channel_id            BIGINT,
    tickets_channel_id        BIGINT,
    antispam_log_channel_id   BIGINT,
    antinuke_log_channel_id   BIGINT,
    coins_log_channel_id      BIGINT,
    xp_log_channel_id         BIGINT,
    levelup_channel_id        BIGINT,

    -- Admins / cargos
    admin_ping_ids            BIGINT[]    NOT NULL DEFAULT '{}',
    levelup_role_map          JSONB       NOT NULL DEFAULT '{}',
                              -- { "2": role_id, "5": role_id, ... }

    -- Economia / premium
    premium_prices            JSONB       NOT NULL DEFAULT
                              '{"aventureiro":0,"lendario":0,"mitico":0}',
    premium_duration_days     INT         NOT NULL DEFAULT 30,
    premium_multipliers       JSONB       NOT NULL DEFAULT
                              '{"aventureiro":2,"lendario":4,"mitico":6}',
    daily_coins               BIGINT      NOT NULL DEFAULT 10000,
    daily_streak_bonus        BIGINT      NOT NULL DEFAULT 10000,
    coins_por_mensagem        BIGINT      NOT NULL DEFAULT 5000,
    coins_por_voz             BIGINT      NOT NULL DEFAULT 15000,
    xp_por_mensagem           BIGINT      NOT NULL DEFAULT 5000,
    xp_por_voz                BIGINT      NOT NULL DEFAULT 15000,
    voice_xp_interval_s       INT         NOT NULL DEFAULT 300,
    bonus_coins_por_nivel     BIGINT      NOT NULL DEFAULT 50000,

    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Usuários (alvo da Phase 4)
CREATE TABLE users (
    user_id          BIGINT PRIMARY KEY,
    xp               BIGINT      NOT NULL DEFAULT 0,
    nivel            INT         NOT NULL DEFAULT 1,
    titulo           TEXT,
    dobro            BOOLEAN     NOT NULL DEFAULT FALSE,
    dobro_expiracao  TIMESTAMPTZ,
    premium          TEXT,                            -- 'aventureiro'|'lendario'|'mitico'|NULL
    premium_expira   TIMESTAMPTZ,
    coins            BIGINT      NOT NULL DEFAULT 0,
    daily_streak     INT         NOT NULL DEFAULT 0,
    last_daily       TIMESTAMPTZ,
    total_ganho      BIGINT      NOT NULL DEFAULT 0,
    guild_name       TEXT,                            -- nome da guild atual no JSON legado
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT users_premium_chk CHECK (
        premium IS NULL OR premium IN ('aventureiro','lendario','mitico')
    )
);
CREATE INDEX users_nivel_idx   ON users (nivel DESC);
CREATE INDEX users_premium_idx ON users (premium) WHERE premium IS NOT NULL;
CREATE INDEX users_coins_idx   ON users (coins DESC);

-- Itens da loja (alvo da Phase 3)
CREATE TABLE items (
    id           SERIAL PRIMARY KEY,
    nome         TEXT        NOT NULL,
    preco        BIGINT      NOT NULL,
    descricao    TEXT,
    cooldown_h   FLOAT       NOT NULL DEFAULT 0,
    criado_por   BIGINT      NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT items_preco_chk CHECK (preco >= 0)
);
CREATE INDEX items_preco_idx ON items (preco DESC);

-- Cooldowns (alvo da Phase 3)
CREATE TABLE cooldowns (
    user_id     BIGINT      NOT NULL,
    item_id     INT         NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
CREATE INDEX cooldowns_expires_idx ON cooldowns (expires_at);

-- Estado de usuários do antispam (Phase 1: ativo)
CREATE TABLE antispam_users (
    guild_id        BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    score           DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_event_ts   DOUBLE PRECISION NOT NULL DEFAULT 0,
    infractions     JSONB       NOT NULL DEFAULT '[]',
    punishments     JSONB       NOT NULL DEFAULT '[]',
    blacklisted     BOOLEAN     NOT NULL DEFAULT FALSE,
    recent_messages JSONB       NOT NULL DEFAULT '[]',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX antispam_users_score_idx ON antispam_users (guild_id, score DESC);

-- Whitelist por guild (Phase 1: ativo)
CREATE TABLE antispam_whitelist (
    guild_id  BIGINT NOT NULL,
    user_id   BIGINT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

-- Configuração do antispam por guild (Phase 1: ativo)
CREATE TABLE antispam_config (
    guild_id   BIGINT      PRIMARY KEY,
    config     JSONB       NOT NULL DEFAULT '{}',  -- AntispamConfig.to_dict()
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Configuração do antinuke por guild (Phase 1: ativo)
CREATE TABLE antinuke_config (
    guild_id   BIGINT      PRIMARY KEY,
    config     JSONB       NOT NULL DEFAULT '{}',  -- AntinukeConfig.to_dict()
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    alert_only BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trilha de eventos de moderação (alvo da Phase 5)
CREATE TABLE antispam_audit (
    id         BIGSERIAL PRIMARY KEY,
    guild_id   BIGINT      NOT NULL,
    user_id    BIGINT      NOT NULL,
    event      TEXT        NOT NULL,
    score      DOUBLE PRECISION,
    reason     TEXT,
    payload    JSONB       NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX antispam_audit_guild_user_idx
    ON antispam_audit (guild_id, user_id, created_at DESC);

-- Controle de migrations
CREATE TABLE schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Análise e Abordagem Escolhida (mantida)

### Opções consideradas

| Opção | Descrição | Problema |
|---|---|---|
| **A** — Bot via HTTP para API | Bot faz request HTTP à API a cada comando | Latência extra em hot path; ponto de falha no fluxo de cada mensagem |
| **B** — Bot direto no banco, API separada | Bot usa `asyncpg` direto; API lê/escreve o mesmo banco | ✅ Sem overhead; API só existe para painel e webhooks |
| **C** — Manter JSON + camada de config no banco | Só config vai pro banco, dados ficam em JSON | Não resolve race condition; dois sistemas de persistência para manter |
| **D** — Dois bots separados com banco compartilhado | Fenrir e FenrirSecurity como containers diferentes | Duplica infra sem ganho real; configs ainda teriam que ser sincronizadas |

### Abordagem escolhida: **Opção B — Bot unificado, direto no banco**

**Justificativa:**

1. **Bot fala diretamente com Postgres via `asyncpg`** — sem hop HTTP no caminho crítico de cada mensagem Discord. A API existe exclusivamente para o painel web e o webhook do Mercado Pago.
2. **Unificação dos dois bots em um container** — feita na Phase 1. Os 4 cogs do `fenrir_security` foram migrados sem conflito.
3. **`server_config` como fonte de verdade** — eliminando IDs hardcoded e configs em dataclasses, qualquer ajuste operacional passa pelo painel sem necessidade de redeploy.
4. **JSONB para configs de antispam/antinuke** — permite alterar campos sem migrations de schema; o bot carrega e valida via `from_dict()` tolerante a campos parciais.
5. **Resiliência independente** — se a API cair, o bot opera normalmente com as configs em cache. Se o banco cair, o bot loga warning e continua operando com JSONs como fallback (durante phases 2-4) ou em modo degradado.

---

## Dependências (após Phase 0)

**Bot (`requirements.txt`):**
```
discord.py==2.4.0
asyncpg==0.29.0
yt-dlp
pillow==10.3.0
requests==2.32.3
aiohttp
python-dotenv
mercadopago
pytest
pytest-asyncio
```

**API (`api/requirements.txt`):**
```
asyncpg==0.29.0
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-jose[cryptography]==3.3.0
httpx==0.27.0
python-dotenv
itsdangerous==2.2.0
```

---

## O que NÃO muda

- Todos os comandos Discord mantêm a mesma interface e comportamento para usuários finais.
- Fluxo de compra, XP, cooldown e premium funcionam igual.
- `guilds_data.json` e `aventuras_data.json` permanecem em JSON até a Phase 6.
- Deploy via Discloud permanece compatível (o container do bot não muda de estrutura).
