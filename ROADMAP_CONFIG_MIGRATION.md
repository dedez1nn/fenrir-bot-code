# Roadmap Técnico: Migração para Arquitetura de Configuração Separada

**Projeto:** Fenrir Discord Bot  
**Versão de referência:** pós-Fase 6 (branch `main`, PostgreSQL unificado)  
**Fontes:** `CLAUDE.md`, `erros_config.md`  
**Objetivo:** migrar do modelo atual (IDs hardcoded + configuração global implícita) para uma arquitetura com separação explícita entre configuração global do produto e configuração por escopo (guild, usuário, módulo).

---

## 1. Diagnóstico do Estado Atual

### 1.1 O que já funciona bem

O projeto concluiu seis fases de migração e possui fundação sólida:

- `server_config` (tabela Postgres + cache 5min) cobre canais, multiplicadores, daily, XP rates e role map.
- `antispam_config` e `antinuke_config` são JSONB tolerantes, editáveis via API com NOTIFY automático.
- LISTEN/NOTIFY via `fenrir_cache` garante invalidação cross-process sem restart.
- Todas as cogs críticas implementam `cog_load` + `self.use_db` + fallback JSON.
- API FastAPI com `require_admin` aplicado em antispam e antinuke.

### 1.2 O que está incompleto ou problemático

**Configuração global do produto não existe como entidade formal.** Parâmetros que pertencem ao dono do bot estão espalhados em arquivos Python, `.env`, `002_seed.sql` e variáveis locais de função.

**Configuração por servidor é parcial.** `server_config` cobre bem os parâmetros de economia, mas canais de moderação, categorias de tickets, cargos de cor, regras de aventura/raid e catálogo premium ainda dependem de IDs hardcoded.

**Todas as cogs carregam por padrão.** Não existe mecanismo de feature flag; uma cog com configuração ausente opera em modo degradado silencioso em vez de comunicar o problema.

**Divergência de valores entre cogs.** `coins_por_mensagem` e `coins_por_voz` têm defaults diferentes em `xp.py` e `fenrir_coins.py`. Não existe fonte única.

**API com auth incompleto.** `/config`, `/items` e `/users` ainda não usam `Depends(require_admin)`. `PATCH /users/{id}/premium` não emite NOTIFY.

**Seed acoplado ao servidor original.** `002_seed.sql` embute IDs reais de produção, tornando setup em ambiente novo ambíguo.

---

## 2. Inventário de Pontos Hardcoded

### 2.1 Configuração global do produto (dono do bot)

| # | Parâmetro | Localização atual | Problema |
|---|---|---|---|
| G1 | Guild principal do bot | `main.py:27` — fallback `1426202696955986022` | qualquer ambiente secundário usa o ID errado |
| G2 | Guild do OAuth | `api/routers/auth.py:37` | depende de `GUILD_ID` env, sem fallback documentado |
| G3 | TTL do cache de config | `db/config.py:20` — `300s` fixo | não ajustável por ambiente |
| G4 | TTL da sessão JWT | `api/routers/auth.py:32` — `12h` | sem configuração por ambiente |
| G5 | Redirect URI OAuth | `api/routers/auth.py:29` — default local | já usa env mas o default é frágil |
| G6 | Tamanhos do pool DB/API | `db/pool.py`, `api/db.py` | fixos, sem tuning por ambiente |
| G7 | Catálogo premium | `cogs/economia/pix.py:28-42` | preços, planos e cargos hardcoded |
| G8 | Recompensas premium | `cogs/economia/pix.py` | coins/XP por plano fixos |
| G9 | Termos proibidos em título | `cogs/economia/compra.py:28` | lista fixa no código |
| G10 | Assets CDN (imagens) | vários arquivos | URLs hardcoded de imagens |
| G11 | Branding (nome, versão) | vários arquivos | texto fixo |
| G12 | Seed inicial de IDs | `db/migrations/002_seed.sql` | acoplado ao servidor de produção |

### 2.2 Configuração por servidor (cogs)

#### Canais e categorias

| # | Parâmetro | Localização | Cog |
|---|---|---|---|
| S1 | Canal log de entrada | `moderacao/entrada.py:9` | `MemberLogs` |
| S2 | Canal de dúvidas | `moderacao/entrada.py:27` | `MemberLogs` |
| S3 | Canal log de saída | `moderacao/entrada.py:51` | `MemberLogs` |
| S4 | Categorias de tickets (suporte/doação/outro) | `moderacao/tickets.py:27-30` | `TicketCog` |
| S5 | Canal de logs de ticket | `moderacao/tickets.py:258-259` | `TicketCog` |
| S6 | Canal criador de call | `moderacao/cria_canal.py:179` | `VoiceCreator` |
| S7 | Canal de changelog | `interface/status.py:16` | `StatusCog` |
| S8 | Canal log de aventuras | `progressao/aventurar.py:356,427,499` | `AventuraCog` |
| S9 | Canal de alianças/raids | `progressao/guild_2.py:777,877,923` | `GuildAllianceRaidSystem` |

#### Cargos

| # | Parâmetro | Localização | Cog |
|---|---|---|---|
| S10 | Staff de ticket (fundador/developer) | `tickets.py:49-53,303-320` | `TicketCog` |
| S11 | Cargos de cores gratuitas | `enviar_cores.py:4-10` | `EnviarCores` |
| S12 | Cargos de cores premium | `enviar_cores.py:11-16`, `compra.py:81-85` (duplicado e divergente) | `EnviarCores`, `CompraCog` |
| S13 | Cargo de item especial | `compra.py:549` | `CompraCog` |

#### Regras operacionais

| # | Parâmetro | Cog(s) | Problema |
|---|---|---|---|
| S14 | XP por vitória | `xp.py:328` | não está em `server_config` |
| S15 | Coins por vitória | `xp.py:331` | não está em `server_config` |
| S16 | Cooldown de XP por mensagem | `xp.py:320` — `10s` | não está em `server_config` |
| S17 | Cooldown de coins por mensagem | `fenrir_coins.py:199` — `180s` | não está em `server_config` |
| S18 | `coins_por_mensagem` divergente | `xp.py:329` vs `fenrir_coins.py:198` | dois defaults diferentes |
| S19 | `coins_por_voz` divergente | `xp.py:330` vs `fenrir_coins.py:200` | dois defaults diferentes |
| S20 | XP base de guild | `guild.py:23` | hardcoded |
| S21 | Recompensas por nível de guild | `guild.py:24-40` | tabela fixa |
| S22 | Cooldown de raid | `guild.py:1437-1439` — `86400s` | hardcoded |
| S23 | Parâmetros de aventura | `aventurar.py:18-36` | chances, recompensas, XP fixos |
| S24 | Cooldowns JSON por posição | `cooldown.py:19-29` | frágil por índice, não por item |

---

## 3. Critérios para Decidir Global vs Por Servidor

### É configuração global do produto quando:

- O valor pertence à instância do bot, não a um servidor específico.
- Mudar o valor afeta todos os servidores igualmente.
- Apenas o dono do bot tem autoridade para alterar.
- Exemplos: credenciais de API externas, catálogo de planos premium, branding, parâmetros de infraestrutura, TTLs de sessão.

### É configuração por servidor quando:

- O valor representa uma escolha do administrador do servidor Discord.
- Servidores diferentes podem ter valores diferentes para o mesmo parâmetro.
- O painel web de cada servidor pode modificar independentemente.
- Exemplos: canais de log, cargos, thresholds de moderação, regras de XP/coins, categorias de ticket.

### É configuração por módulo (feature config) quando:

- O valor configura um módulo específico que pode estar habilitado ou não.
- Depende da feature estar ativa para ter significado.
- Exemplos: `antispam_config`, `antinuke_config`, e futuramente `tickets_config`, `adventure_config`.

### É configuração por usuário quando:

- O valor pertence ao estado individual de um membro.
- Exemplos: preferências de notificação, títulos, opt-in/opt-out de features. *(Fora do escopo desta migração, mas deve ser preparada conceitualmente.)*

---

## 4. Dependências entre Módulos

```
FenrirCoins ←── XPCog
FenrirCoins ←── LojaCog ←── CompraCog ←── ComandosLojaCog
FenrirCoins ←── PixCog
FenrirCoins ←── GuildSystem ←── GuildAllianceRaidSystem
FenrirCoins ←── AventuraCog
XPCog       ←── AventuraCog
XPCog       ←── GuildAllianceRaidSystem
GuildSystem ←── GuildAllianceRaidSystem
LojaCog     ←── CompraCog
CooldownCog ←── CompraCog
CooldownCog ←── LojaCog
```

**Cogs independentes (sem dependência de outra cog):**
`AntiNuke`, `AntiSpam`, `InviteBlocker`, `AutoRemoveBots`, `RiotCog`, `SteamCog`, `GNewsCog`, `MemberLogs`, `TicketCog`, `VoiceCreator`, `AddRole`, `ClearMessages`, `StatusCog`, `HelpCog`, `EnviarCores`

**Dependências críticas de configuração (impedem operação se ausentes):**

| Cog | Depende de (config) |
|---|---|
| `TicketCog` | categorias, staff roles, canal de log |
| `VoiceCreator` | canal base de voz |
| `EnviarCores` | ao menos um cargo de cor |
| `PixCog` | `ACCESS_TOKEN`, catálogo premium, cargos premium |
| `XPCog` (cargos por nível) | `levelup_role_map` válido |
| `GuildAllianceRaidSystem` | canal de raid |
| `MemberLogs` | canais de entrada/saída |
| `RiotCog` / `SteamCog` / `GNewsCog` | API key respectiva |
| `AntiNuke` (modo ativo) | permissões `Manage Channels` + `Kick Members` |
| `AntiSpam` | permissão `Manage Messages` |

---

## 5. Ordem Recomendada das Mudanças

A ordem segue o princípio: **fundar antes de construir**. Cada etapa entrega valor independente e não quebra o que existe.

```
[Etapa 0] Consolidar divergências de valores (sem schema novo)
    ↓
[Etapa 1] Formalizar global_config como entidade
    ↓
[Etapa 2] Migrar hardcoded de servidor para server_config (canais/cargos)
    ↓
[Etapa 3] Migrar regras operacionais para server_config
    ↓
[Etapa 4] Extrair configs de features para server_feature_config
    ↓
[Etapa 5] Implementar feature flags + validação preventiva nas cogs
    ↓
[Etapa 6] Fechar gaps de auth e NOTIFY na API
    ↓
[Etapa 7] Preparar contratos de leitura/escrita para painel web
```

---

## 6. Plano em Fases

---

### ✅ Fase 0 — Consolidação de Divergências — CONCLUÍDA

- `xp_por_vitoria`, `coins_por_vitoria`, `xp_message_cooldown_s`, `coins_message_cooldown_s` adicionados a `server_config` via `db/migrations/004_config_fields.sql`.
- `xp.py` e `fenrir_coins.py` leem exclusivamente de `bot.config`; defaults locais removidos.
- `pytest -q` passa sem regressão.

---

### ✅ Fase 1 — Formalizar `global_config` — CONCLUÍDA

- Tabela `global_config` criada via `db/migrations/005_global_config.sql` com seed de parâmetros G1–G6.
- `db/global_config.py`: `GlobalConfig` wrapper com cache TTL e `load_global_config(pool)`.
- `bot.global_config` populado em `_init_database()`; TTL de `server_config` lido dinamicamente.
- `main.py` usa `global_config.get("primary_guild_id")` para resolver guild; sem ID hardcoded.
- `GET/PATCH /global-config` exposto na API com `require_admin`.

---

### ✅ Fase 2 — Migrar Canais e Cargos Hardcoded para `server_config` — CONCLUÍDA

- 14 novas colunas adicionadas via `db/migrations/006_server_config_channels.sql` (S1–S13).
- Seed com IDs de produção em `db/migrations/007_seed_channels.sql`.
- Cogs migradas: `MemberLogs`, `TicketCog`, `VoiceCreator`, `StatusCog`, `AventuraCog`, `GuildAllianceRaidSystem`, `EnviarCores`, `CompraCog`.
- Nenhum `get_channel(ID_LITERAL)` ou `get_role(ID_LITERAL)` restante nas cogs migradas.

---

### ✅ Fase 3 — Migrar Regras Operacionais e Catálogo Premium — CONCLUÍDA

- Colunas operacionais adicionadas via `db/migrations/008_server_config_rules.sql` (`guild_xp_base`, `guild_level_rewards`, `guild_raid_cooldown_s`, `adventure_chances`, `adventure_rewards`).
- `guild.py` e `aventurar.py` leem esses parâmetros de `bot.config` com fallbacks seguros.
- Tabela `premium_catalog` criada via `db/migrations/009_premium_catalog.sql` com seed dos 3 planos (aventureiro, lendario, mitico).
- `repositories/premium.py` criado; `PixCog.cog_load` carrega catálogo do DB.
- `GET /premium/catalog` e `PUT /premium/catalog/{plan_key}` com `require_admin` expostos na API.

---

### ✅ Fase 4 — Extrair Configurações de Features para `server_feature_config` — CONCLUÍDA

**Objetivo:** Criar entidade formal para configuração por feature/módulo, preparando para feature flags.

#### Tarefas

4.1. **Criar tabela `server_feature_config`**

```sql
-- db/migrations/009_feature_config.sql
CREATE TABLE IF NOT EXISTS server_feature_config (
    guild_id    BIGINT NOT NULL,
    feature     TEXT NOT NULL,
    enabled     BOOLEAN DEFAULT FALSE,
    config      JSONB DEFAULT '{}',
    validated   BOOLEAN DEFAULT FALSE,
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (guild_id, feature)
);
```

4.2. **Features iniciais a mapear:**

| Feature key | Cog(s) | Config relevante |
|---|---|---|
| `tickets` | `TicketCog` | categorias, staff, log |
| `voice_creator` | `VoiceCreator` | canal base |
| `member_logs` | `MemberLogs` | canais join/leave |
| `colors` | `EnviarCores` | role lists |
| `adventures` | `AventuraCog` | regras de aventura |
| `guild_raids` | `GuildAllianceRaidSystem` | canal, cooldown |
| `riot` | `RiotCog` | API key (referência) |
| `steam` | `SteamCog` | API key (referência) |
| `gnews` | `GNewsCog` | API key (referência) |
| `antispam` | `AntiSpam` | thresholds, ladder |
| `antinuke` | `AntiNuke` | thresholds, mode |

4.3. **Criar `FeatureConfig` wrapper** em `db/feature_config.py`:

```python
async def get_feature_config(pool, guild_id, feature) -> dict | None
async def set_feature_config(pool, guild_id, feature, config, enabled) -> None
async def is_feature_enabled(pool, guild_id, feature) -> bool
```

4.4. **Integrar com NOTIFY:** `pg_notify('fenrir_cache', 'feature:{guild_id}:{feature}')` ao salvar.

4.5. **Migrar `antispam_config` e `antinuke_config`:**  
*Não mover o storage JSONB* — ele já funciona bem. Apenas adicionar uma linha em `server_feature_config` como fonte de `enabled`. O `config` JSONB permanece nas tabelas dedicadas para não quebrar a edição existente.

4.6. **Seed inicial:** inserir linha `enabled = TRUE` para cada feature que já opera no servidor de produção.

**Critério de conclusão:** `server_feature_config` existe e tem linhas seed; `is_feature_enabled` funciona; NOTIFY emitido corretamente; sem regressão.

Implementação: `db/migrations/010_feature_config.sql`, `db/feature_config.py`, `db/validators.py`.

---

### ✅ Fase 5 — Feature Flags e Validação Preventiva nas Cogs — CONCLUÍDA

**Objetivo:** Cogs verificam se sua feature está habilitada; features com configuração inválida comunicam o problema em vez de falhar silenciosamente.

**Objetivo:** Cogs verificam se sua feature está habilitada; features com configuração inválida comunicam o problema em vez de falhar silenciosamente.

#### Tarefas

5.1. **Adicionar verificação de feature em `cog_load`:**

```python
async def cog_load(self):
    self.use_db = self.bot.db is not None
    self.feature_enabled = await is_feature_enabled(
        self.bot.db, GUILD_ID, "tickets"
    ) if self.use_db else True  # fallback: habilitar no modo legado
```

5.2. **Adicionar guard de feature nos comandos:**

```python
if not self.feature_enabled:
    await interaction.response.send_message(
        "Este recurso não está habilitado neste servidor.", ephemeral=True
    )
    return
```

5.3. **Implementar `validate_feature_config()`** em cada cog configurável:

```python
async def validate_feature_config(self) -> list[str]:
    """Retorna lista de erros de configuração. Lista vazia = config válida."""
    errors = []
    if not self.bot.config.get("ticket_support_category_id"):
        errors.append("CONFIG_MISSING_CATEGORY: categoria de suporte não configurada")
    if not self.bot.config.get("ticket_staff_role_ids"):
        errors.append("CONFIG_MISSING_ROLE: staff de ticket não configurado")
    return errors
```

5.4. **Usar códigos de erro do catálogo definido em `erros_config.md` seção 5:**  
`CONFIG_MISSING_CHANNEL`, `CONFIG_MISSING_ROLE`, `CONFIG_MISSING_CATEGORY`, `CONFIG_MISSING_API_KEY`, `CONFIG_INVALID_ROLE_MAP`, `CONFIG_INVALID_PREMIUM_PLAN`, `CONFIG_INVALID_THRESHOLD`, `CONFIG_PERMISSION_BOT`.

5.5. **Criar endpoint de validação na API:**  
`GET /features/{guild_id}/validation` — retorna estado de validação de todas as features com lista de erros por feature.

5.6. **Prioridade de implementação de `validate_feature_config`:**

1. `TicketCog` (múltiplas dependências críticas)
2. `PixCog` (risco financeiro)
3. `XPCog` (cargos por nível)
4. `VoiceCreator`
5. `AntiNuke` (modo ativo)
6. demais cogs

**Critério de conclusão:** toda cog configurável expõe `validate_feature_config()`; `GET /features/{guild_id}/validation` retorna resultado correto; nenhum crash silencioso documentado.

Implementação: `feature_enabled` em `MemberLogs`, `VoiceCreator`, `TicketCog`, `InviteBlocker`, `AutoRemoveBots`; `validate_feature_config()` nos cogs prioritários; `GET/PUT /features/{guild_id}` na API; NOTIFY `feature:{guild_id}:{feature}` + handler em `main.py`.

---

### ✅ Fase 6 — Fechar Gaps de Auth e NOTIFY na API — CONCLUÍDA

**Objetivo:** Garantir que mutações da API sejam autenticadas e que o cache seja invalidado em todos os casos.

#### Tarefas

6.1. **Adicionar `Depends(require_admin)` nos routers pendentes:**  
- `POST/PUT/DELETE /items`  
- `PUT /config/{guild_id}` (já tem, verificar)  
- `PUT/PATCH /users/{user_id}` (exceto rotas públicas)  
- `PUT /global-config/{key}` (criado na Fase 1)

6.2. **Adicionar NOTIFY em `PATCH /users/{user_id}/premium`:**

```python
await conn.execute(
    "SELECT pg_notify('fenrir_cache', $1)",
    f"user:{user_id}"
)
```

6.3. **Adicionar NOTIFY em todas as mutações de `server_feature_config`:**  
`pg_notify('fenrir_cache', f'feature:{guild_id}:{feature}')` após PATCH.

6.4. **Atualizar `_start_cache_listener()` em `main.py`** para tratar `feature:{guild_id}:{feature}`:

```python
elif kind == "feature":
    guild_id, feature = parts[1], parts[2]
    # reload feature_enabled para a cog afetada
    cog = self.get_cog(FEATURE_TO_COG_MAP.get(feature))
    if cog and hasattr(cog, "reload_feature_state"):
        await cog.reload_feature_state()
```

6.5. **Remover seed de IDs de servidor do `002_seed.sql`:**  
Mover os IDs de produção para um arquivo `.env`-driven ou para setup interativo, evitando vazar IDs em repositório público.

6.6. **Documentar o contrato NOTIFY completo** em `CLAUDE.md`:

```
fenrir_cache payloads:
  user:{id}           → reload user cache
  premium:{id}:{plan} → reload cache + grant_premium_rewards
  config:{guild_id}   → reload server_config
  antispam:{guild_id} → reload antispam config
  antinuke:{guild_id} → reload antinuke config
  feature:{guild_id}:{feature} → reload feature flag
```

**Critério de conclusão:** nenhum endpoint mutante sem `require_admin`; todos os NOTIFYs documentados e testados; `pytest -q` passa.

Implementação: `require_admin` em `POST/PATCH/DELETE /items`, `PATCH /config/{guild_id}`, `PATCH /users/{id}/premium`; NOTIFY `user:{id}` em `PATCH /users/{id}/premium`; NOTIFY `feature:{guild_id}:{feature}` em `PUT /features/{guild_id}/{feature}`; contrato NOTIFY documentado em `CLAUDE.md`.

---

### Fase 7 — Preparar Contratos para o Painel Web

**Objetivo:** Expor na API tudo que o painel web precisará consumir, com schema de validação explícito.

#### Tarefas

7.1. **Endpoint de configuração por servidor (leitura completa):**  
`GET /server/{guild_id}/config` — retorna `server_config` + estado de todas as features + erros de validação.

7.2. **Endpoint de patch parcial:**  
`PATCH /server/{guild_id}/config` — aceita campos parciais, valida referências Discord (canal/cargo existe?), valida compatibilidade entre campos, persiste, emite NOTIFY.

7.3. **Validação de referências Discord antes de persistir:**

```python
async def validate_discord_references(guild_id, config_patch):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise ConfigError("Guild não encontrada")
    if "ticket_log_channel_id" in config_patch:
        ch = guild.get_channel(config_patch["ticket_log_channel_id"])
        if not ch:
            raise ConfigError("CONFIG_MISSING_CHANNEL: canal de log de ticket inválido")
```

7.4. **Endpoint de habilitação/desabilitação de feature:**  
`PUT /features/{guild_id}/{feature}/toggle` — valida `validate_feature_config()` antes de habilitar; emite NOTIFY.

7.5. **Schema de resposta padronizado para erros:**

```json
{
  "error_code": "CONFIG_MISSING_CHANNEL",
  "feature": "tickets",
  "field": "ticket_log_channel_id",
  "message": "Configure o canal de logs de ticket antes de ativar Tickets.",
  "suggestion": "Abra Configurações > Canais e selecione um canal válido."
}
```

7.6. **Documentação OpenAPI:** garantir que todos os endpoints novos tenham `summary`, `description` e exemplos de resposta para que o painel possa consumir o schema automaticamente.

**Critério de conclusão:** painel web pode consumir a API para ler, editar e habilitar qualquer feature sem consultar o código do bot.

---

### ✅ Fase 7 — Dashboard Unificado para o Painel Web — CONCLUÍDA


**Objetivo:** Expor via API tudo que o painel precisa em uma única chamada GET, eliminar round-trips múltiplos.

#### Tarefas

7.1. **`GET /server/{guild_id}`** — endpoint unificado retornando:
- `server_config`: todos os campos da config do servidor
- `features`: dict feature → {enabled, config, validation: {is_valid, errors}}
- `premium_catalog`: planos ativos ordenados por preço

7.2. **`GET /server/{guild_id}/audit`** — histórico paginado de alterações (implementado na Fase 9).

7.3. **Schema padronizado de erro** — já provido por `db/validators.py` com campos `code`, `field`, `message`, `suggestion`.

Implementação: `api/routers/server.py` registrado em `api/main.py`.

**Critério de conclusão:** painel pode obter toda a informação de configuração em um único GET sem requerer múltiplas chamadas paralelas.

---

### ✅ Fase 8 — Feature Flags nas Cogs Econômicas e Health Check de Config — CONCLUÍDA

**Objetivo:** Completar a cobertura de feature flags nas cogs de progressão/economia e expor um diagnóstico de saúde de configuração acessível pelo bot e pelo painel.

#### Tarefas

8.1. **Adicionar `feature_enabled` às cogs restantes:**

| Cog | Feature key | Listener/comando guarded |
|---|---|---|
| `XPCog` | `xp` | `on_message` (XP automático por chat) |
| `AventuraCog` | `adventures` | `/aventura` (já tem cog_load, add flag) |
| `PixCog` | `premium` | carregar catálogo + grant rewards |

8.2. **`validate_feature_config()` nas cogs sem ela:**
- `AventuraCog`: verifica `adventure_log_channel_id`
- `MemberLogs`: delega a `validate_member_logs` de `db/validators.py`

8.3. **`FenrirBot._check_config_health()`** em `main.py`:
- Roda `validate_all(config.to_dict())` e loga warnings para cada feature com erros
- Chamado em `on_ready` após todos os cogs carregarem
- Rechamado quando NOTIFY `config:{guild_id}` é recebido

8.4. **Slash command `/config_status`** — admin only, exibe embed com estado de validação de todas as features (canais, roles, API keys). Cog: `cogs/interface/config_check.py`.

**Critério de conclusão:** toda cog com listeners automáticos respeita feature flag; bot loga saúde da config em cada boot; `/config_status` retorna diagnóstico sem acessar o DB diretamente no comando.

---

### ✅ Fase 9 — Auditoria de Alterações de Configuração — CONCLUÍDA

**Objetivo:** Registrar quem alterou o quê e quando, permitindo rastrear mudanças que causaram comportamento inesperado.

#### Tarefas

9.1. **Criar tabela `config_audit_log`** via `db/migrations/011_config_audit_log.sql`:

```sql
CREATE TABLE IF NOT EXISTS config_audit_log (
    id         BIGSERIAL    PRIMARY KEY,
    guild_id   BIGINT       NOT NULL,
    changed_by TEXT         NOT NULL,   -- Discord user ID (JWT sub)
    kind       TEXT         NOT NULL,   -- 'server_config' | 'feature' | 'global_config'
    target     TEXT,                    -- feature name ou config key
    patch      JSONB        NOT NULL DEFAULT '{}',
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cal_guild_idx ON config_audit_log (guild_id);
CREATE INDEX IF NOT EXISTS cal_time_idx  ON config_audit_log (changed_at DESC);
```

9.2. **Escrever audit entry (best effort)** em todos os endpoints que mutam config:
- `PATCH /config/{guild_id}` → kind `server_config`, patch = corpo da requisição
- `PUT /features/{guild_id}/{feature}` → kind `feature`, target = feature name, patch = `{enabled: ...}`
- `PATCH /global-config/{key}` → kind `global_config`, target = key

9.3. **`GET /server/{guild_id}/audit`** em `api/routers/server.py`:
- Requer admin
- Paginação por `page`/`per_page`
- Filtro opcional por `kind`

9.4. **Audit ID como fingerprint** — response de PATCH/PUT inclui `audit_id` no campo `meta` para correlação com logs.

**Critério de conclusão:** toda alteração de config via API tem registro auditável; `GET /server/{guild_id}/audit` retorna histórico correto; sem overhead perceptível (INSERT é fire-and-forget em conexão separada).

---

### ✅ Fase 10 — Feature Flags via `interaction_check` nas Cogs Restantes — CONCLUÍDA

**Objetivo:** Cobrir todos os cogs com slash commands com feature flag, usando `interaction_check` como ponto único de controle por cog.

#### Tarefas

10.1. **Helper `load_feature_state_for_cog(bot, feature)` em `db/feature_config.py`**
Centraliza a lógica de leitura de feature flag nos cogs, eliminando código duplicado.

10.2. **Cogs a receber `feature_enabled` + `interaction_check` + `reload_feature_state`:**

| Cog | Feature key | Tem cog_load? |
|---|---|---|
| `FenrirCoins` | `economy` | Sim, adicionar ao fim |
| `GuildSystem` | `guilds` | Sim, adicionar ao fim |
| `GuildAllianceRaidSystem` | `guild_raids` | Sim, adicionar ao fim |
| `RiotCog` | `riot` | Não, criar |
| `SteamCog` | `steam` | Não, criar |
| `GNewsCog` | `gnews` | Não, criar |

10.3. **`interaction_check(interaction)` em cada cog:**
Retorna `False` e responde com mensagem ephemeral quando `feature_enabled=False`, bloqueando todos os slash commands do cog sem necessidade de guards por comando.

10.4. **Atualizar `_FEATURE_COG_MAP` em `main.py`** para mapear `guilds`, `riot`, `steam`, `gnews`.

**Critério de conclusão:** 100% das cogs com slash commands respeitam feature flag; `PUT /features/{guild_id}/{feature}` + NOTIFY desativa qualquer cog dinamicamente sem restart.

---

### ✅ Fase 11 — Feature Config JSONB por Feature — CONCLUÍDA

**Objetivo:** Usar a coluna `config JSONB` de `server_feature_config` para armazenar configurações simples por feature, evitando novas colunas em `server_config` para parâmetros feature-específicos.

#### Tarefas

11.1. **`get_feature_config(pool, guild_id, feature) -> dict` em `db/feature_config.py`**

11.2. **`PATCH /features/{guild_id}/{feature}/config`** — mescla com config existente via `||` JSONB; emite NOTIFY `feature:` e grava audit.

11.3. **Cogs que leem feature config:**

| Cog | Chave lida | Efeito |
|---|---|---|
| `VoiceCreator` | `channel_name_prefix` (default `"🔊 Sala de"`) | Nome dos canais criados |
| `XPCog` | `blacklisted_channel_ids` (default `[]`) | Canais onde XP não é ganho |
| `MemberLogs` | `welcome_image_url` (default: CDN original) | Imagem no embed de boas-vindas |

11.4. **`reload_feature_state()` recarrega config JSONB** além do flag `enabled`.

**Critério de conclusão:** feature config é editável via API e aplicada pelo bot sem restart; `PATCH /features/{guild_id}/voice_creator/config` com `{"channel_name_prefix": "🎮 Sala de"}` muda o comportamento imediatamente.

---

### ✅ Fase 12 — Audit Completo + Bulk Feature Toggle — CONCLUÍDA

**Objetivo:** Cobrir todos os endpoints mutantes com auditoria e adicionar operação em lote para features.

#### Tarefas

12.1. **Audit nos endpoints restantes:**
- `PATCH /antispam/config/{guild_id}` → kind `antispam_config`
- `PATCH /antinuke/config/{guild_id}` → kind `antinuke_config`
- `PATCH /global-config/{key}` → kind `global_config`, target = key, guild_id = 0

12.2. **`PUT /features/{guild_id}/bulk`** — toggle múltiplas features de uma vez:
```json
{"tickets": true, "voice_creator": false, "xp": true}
```
Emite um NOTIFY por feature alterada e grava um audit entry por feature.

12.3. **`dependencies=[Depends(require_admin)]` → `user=Depends(require_admin)`** nos endpoints de antispam e antinuke para expor o usuário ao audit.

**Critério de conclusão:** toda mutação de config (antispam, antinuke, global, bulk features) aparece em `GET /server/{guild_id}/audit`; bulk toggle emite NOTIFY para cada feature afetada.

---

## 7. Estratégia de Migração sem Quebrar Compatibilidade

### Princípio: Expand-and-Contract

Cada campo novo passa por três estágios:

```
1. Additive (não quebra nada):
   - Adicionar coluna nullable em server_config
   - Adicionar novo getter em ServerConfig com fallback ao hardcode

2. Migration (sem breaking change):
   - Preencher a coluna com o valor que estava hardcoded (via seed/migration)
   - Cog lê do config, fallback ao default embutido se None

3. Contraction (remove o hardcode):
   - Remover o literal do código
   - A cog exige que o campo esteja preenchido (ou loga warning e opera degradado)
```

### Exemplo prático: migrar `adventure_log_channel_id`

```python
# Estágio 1 (antes da migration de schema):
ADVENTURE_LOG_CH = 987654321  # legado, provisório

channel_id = self.bot.config.get("adventure_log_channel_id") or ADVENTURE_LOG_CH

# Estágio 2 (após migration, antes de remover hardcode):
channel_id = self.bot.config.get("adventure_log_channel_id") or ADVENTURE_LOG_CH
# migration 005 já populou a coluna com o valor correto

# Estágio 3 (hardcode removido):
channel_id = self.bot.config.get("adventure_log_channel_id")
if not channel_id:
    logger.warning("adventure_log_channel_id não configurado; log de aventura desativado")
    return
```

### Regra geral de fallback durante a transição

Para cada campo migrado, aplicar na ordem:

1. `bot.config.get("campo")` — DB (fonte principal)
2. `bot.global_config.get("campo")` — global config, se aplicável
3. `DEFAULT_VALOR` — constante Python com nome descritivo (nunca literal nu)
4. `None` + `logger.warning(...)` + skip da funcionalidade, sem crash

---

## 8. Regras para Fallback e Valores Padrão

### Hierarquia de fallback

```
Postgres (server_config / global_config)
    ↓ se campo None ou DB indisponível
Constante DEFAULT_* no módulo (nunca literal nu)
    ↓ se operação crítica
Log warning + retorno gracioso (nunca crash)
```

### Convenções de código

- Defaults nomeados no topo do módulo:  
  `DEFAULT_RAID_COOLDOWN_S = 86400` — não `86400` inline.
- Defaults em `server_config` devem ser idênticos às constantes Python para consistência.
- Fallback JSON ativado apenas quando `self.bot.db is None` — nunca como alternativa a campo vazio no DB.
- Campos `BIGINT` de canal/cargo: `None` significa "não configurado, skip"; `0` não é válido, nunca usar como sentinela.
- Arrays (`BIGINT[]`): `[]` vazio é estado válido (feature existe mas sem itens); `NULL` significa "não configurado".

### Defaults canônicos por domínio

| Parâmetro | Default |
|---|---|
| `xp_por_mensagem` | 10 |
| `coins_por_mensagem` | 5 |
| `xp_por_voz` | 5 |
| `coins_por_voz` | 2 |
| `xp_message_cooldown_s` | 10 |
| `coins_message_cooldown_s` | 180 |
| `daily_coins` | 100 |
| `daily_streak_bonus` | 10 |
| `guild_xp_base` | 100 |
| `guild_raid_cooldown_s` | 86400 |
| `server_config_ttl_s` | 300 |
| `admin_session_ttl_h` | 12 |

---

## 9. Estrutura Conceitual de Armazenamento e Leitura

### Entidades de configuração

```
global_config          → chave/valor JSONB global do produto
server_config          → uma linha por guild, colunas tipadas
antispam_config        → JSONB por guild (já existe)
antinuke_config        → JSONB por guild (já existe)
server_feature_config  → (guild_id, feature) → enabled + config JSONB
premium_catalog        → uma linha por plano
```

### Composição em "effective config" (Fase 7)

```python
class EffectiveConfig:
    global_config:  GlobalConfig
    server_config:  ServerConfig
    features:       dict[str, FeatureState]  # feature → {enabled, config, errors}

    def get(self, key):
        # 1. server_config primeiro (sobrescreve global)
        # 2. global_config
        # 3. None
```

### Fluxo de leitura (bot)

```
startup
  ├── load_global_config(pool)   → bot.global_config
  └── load_server_config(pool)   → bot.config

cog_load
  ├── self.use_db = bot.db is not None
  ├── self.feature_enabled = await is_feature_enabled(...)
  └── lê parâmetros de bot.config (com defaults)

comando invocado
  ├── guard_channel (já implementado)
  ├── check feature_enabled
  └── usa bot.config para resolver IDs
```

### Fluxo de escrita (API → NOTIFY → bot)

```
PATCH /server/{guild_id}/config
  ├── validate_schema(patch)
  ├── validate_discord_references(guild_id, patch)
  ├── validate_inter_field_compat(patch)
  ├── UPDATE server_config SET ... WHERE guild_id = $1
  ├── pg_notify('fenrir_cache', f'config:{guild_id}')
  └── return {ok: true, warnings: [...]}

bot cache listener
  ├── recebe 'config:{guild_id}'
  └── await refresh_server_config(pool, guild_id)
      → bot.config atualizado sem restart
```

---

## 10. Riscos, Pontos Críticos e Rollback

### Risco 1: Migração de Schema com Dados de Produção

**Problema:** `ALTER TABLE server_config ADD COLUMN` em produção pode falhar se já existir (idempotência) ou se o Postgres estiver sob carga.

**Mitigação:**
- Todas as migrations usam `IF NOT EXISTS` ou `IF NOT EXISTS + DEFAULT`.
- `db/migrate.py` já garante idempotência via `schema_migrations`.
- Testar migration em clone do DB de produção antes de aplicar.

**Rollback:** colunas adicionais com `DEFAULT` não quebram código antigo; rollback = manter código antigo lendo o default.

---

### Risco 2: Divergência de Valores Durante a Transição (Estágio 1 → 2)

**Problema:** enquanto a cog lê `config.get("campo") or HARDCODE`, qualquer bug na migration de seed pode silenciosamente aplicar o default errado.

**Mitigação:**
- Verificar que o seed/migration insere o valor correto antes de remover o hardcode.
- Adicionar log `DEBUG` temporário: `logger.debug(f"Using {key}={value} (source={'db' if from_db else 'default'})")`.

**Rollback:** reverter a cog ao hardcode sem reverter a migration — o campo fica populado mas sem uso.

---

### Risco 3: Feature Flag Bloquear Funcionalidade Ativa

**Problema:** ao criar `server_feature_config`, a seed inicial pode estar incompleta e `is_feature_enabled` retorna `False` para features que deveriam estar ativas.

**Mitigação:**
- Seed deve inserir `enabled = TRUE` para todas as features atualmente operacionais.
- Fallback de `cog_load`: se não encontrar linha em `server_feature_config` e `self.use_db`, assume `True` (comportamento atual) e loga warning.

```python
self.feature_enabled = await is_feature_enabled(pool, guild_id, feature) 
                        if row_exists else True  # sem linha = funciona como antes
```

**Rollback:** deletar linha da `server_feature_config` → cog assume habilitado.

---

### Risco 4: NOTIFY Perdido (Bot Offline)

**Problema:** bot reiniciado após uma mudança de config via API pode não receber o NOTIFY.

**Mitigação:** `on_ready` e `cog_load` sempre recarregam config do DB — NOTIFY é otimização, não única fonte de verdade.

---

### Risco 5: IDs de Produção em Repositório Público

**Problema:** `002_seed.sql` embute IDs reais.

**Mitigação (Fase 6, item 6.5):**
- Mover valores para `.env` ou para um arquivo `setup/seed_prod.sql` não commitado.
- `002_seed.sql` no repo passa a usar placeholders (`0` ou `NULL`), com comentário instruindo o setup.

**Rollback:** substituir por valores corretos no arquivo — não há dado sensível que não possa ser recriado.

---

### Risco 6: `PremiumCog` e `PixCog` em Conflito

**Problema:** dois sistemas de premium com lógica parcialmente duplicada — uma mudança em `premium_catalog` pode afetar apenas um dos dois.

**Mitigação (Fase 3):** definir formalmente `PixCog` como interface de compra e `PremiumCog` como camada de aplicação de benefícios. Migrar `PremiumCog.aplicar_premium()` para ler do novo `premium_catalog`. Marcar código legado claramente.

---

### Rollback Global

Se qualquer fase precisar ser revertida:

1. `git revert` do commit da fase afetada.
2. As migrations SQL são cumulativas — **não reverter migrations**; adicionar uma nova migration que desfaz a mudança se necessário.
3. Campos adicionados com `DEFAULT` não precisam ser removidos para o código antigo funcionar.

---

## 11. Critérios de Conclusão por Etapa

| Fase | Critério principal | Critério de qualidade |
|---|---|---|
| 0 | Nenhum default duplicado de coins/XP fora de `server_config` | `pytest -q` passa sem regressão |
| 1 | `bot.global_config` disponível; nenhum guild ID hardcoded em `main.py` | Tests de integração cobrem `GlobalConfig` |
| 2 | Nenhum `get_channel(ID_LITERAL)` em cogs | Seed cobre todos os IDs necessários |
| 3 | `premium_catalog` editável via API; nenhuma tabela de preços no Python | `PixCog` e `PremiumCog` sem duplicação de lógica |
| 4 | `server_feature_config` com seed correto; NOTIFY de feature funcional | Todas as features críticas têm linha seed |
| 5 | Todas as cogs configuráveis expõem `validate_feature_config()` | `GET /features/{guild_id}/validation` retorna estado correto |
| 6 | Todos os endpoints mutantes têm `require_admin`; todos os NOTIFYs documentados | Nenhum `PATCH` sem NOTIFY testado |
| 7 | Painel web pode ler, editar e habilitar qualquer feature via API | Schema OpenAPI gerado automaticamente e correto |

---

## 12. Preparação para Futura Integração com Painel Web

### Contratos que o painel vai precisar

**Leitura:**
- `GET /server/{guild_id}/config` — config completa com estado de validação
- `GET /features/{guild_id}/validation` — erros por feature
- `GET /premium/catalog` — planos disponíveis
- `GET /global-config` — parâmetros globais (somente admin)

**Escrita:**
- `PATCH /server/{guild_id}/config` — patch parcial com validação de referências Discord
- `PUT /features/{guild_id}/{feature}/toggle` — habilitar/desabilitar com validação prévia
- `PUT /premium/catalog/{plan_key}` — editar plano premium
- `PATCH /global-config/{key}` — editar parâmetro global (somente admin)

### Formato de resposta para o painel

```json
{
  "guild_id": 123456,
  "server_config": { "xp_por_mensagem": 10, ... },
  "features": {
    "tickets": {
      "enabled": false,
      "config": { "support_category_id": null, ... },
      "validation": {
        "is_valid": false,
        "errors": [
          {
            "code": "CONFIG_MISSING_CATEGORY",
            "field": "ticket_support_category_id",
            "message": "Categoria de suporte não configurada",
            "suggestion": "Abra Configurações > Canais e configure uma categoria"
          }
        ]
      }
    }
  }
}
```

### Princípios para o painel

1. **Painel nunca salva IDs não validados** — sempre verificar existência no Discord antes de persistir.
2. **Painel não habilita feature com erros de validação** — apenas exibe os erros e a sugestão de correção.
3. **Painel reflete NOTIFY em tempo real** — usar WebSocket ou polling curto no `/features/{guild_id}/validation`.
4. **Painel não acessa o DB diretamente** — apenas via API REST; bot e API são as únicas camadas com acesso ao Postgres.
5. **Código de erro padronizado** — usar os códigos definidos em `erros_config.md` seção 5 para internacionalização futura.

### O que NÃO fazer no painel

- Não implementar lógica de negócio no frontend — toda validação de configuração fica no bot/API.
- Não expor `global_config` ao administrador de servidor comum — apenas ao dono do bot.
- Não permitir edição de `premium_catalog` por administrador de servidor — é configuração global.

---

## Resumo Executivo das Fases

| Fase | Nome | Risco | Impacto | Dependência |
|---|---|---|---|---|
| 0 | Consolidar divergências | Baixo | Corretude imediata | Nenhuma |
| 1 | global_config | Baixo | Fundação | Fase 0 |
| 2 | Canais/cargos hardcoded | Médio | Portabilidade | Fase 1 |
| 3 | Regras operacionais + premium_catalog | Médio | Flexibilidade | Fase 2 |
| 4 | server_feature_config | Médio | Estrutura para flags | Fase 3 |
| 5 | Feature flags + validação | Médio-Alto | Observabilidade | Fase 4 |
| 6 | Auth + NOTIFY completos | Baixo-Médio | Segurança | Fase 5 |
| 7 | Dashboard unificado | Baixo | Habilitador | Fase 6 |
| 8 | Feature flags restantes + health check | Baixo | Observabilidade | Fase 7 |
| 9 | Auditoria de configuração | Baixo | Rastreabilidade | Fase 8 |
| 10 | Feature flags via interaction_check | Baixo | Cobertura total | Fase 9 |
| 11 | Feature config JSONB por feature | Baixo | Flexibilidade | Fase 10 |
| 12 | Audit completo + bulk toggle | Baixo | Rastreabilidade | Fase 11 |

**Condição mínima para o painel web funcionar:** Fases 0–6 concluídas. A Fase 7 é a entrega final de habilitação.

**Condição mínima para portabilidade a outro servidor Discord:** Fases 0–3 concluídas. A partir daí, nenhum ID de servidor específico existe no código Python.
