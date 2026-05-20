# Fenrir

Fenrir é um stack para Discord composto por bot, API administrativa e PostgreSQL. O projeto reúne economia, progressão, guilds, aventuras, moderação, integrações externas e pagamento premium via Mercado Pago, com fallback para JSON quando o banco não está disponível.

## Arquitetura

- `main.py` sobe o bot Discord.
- `api/main.py` sobe a API administrativa FastAPI.
- `db/` concentra pool, migrações e cache de `server_config`.
- `repositories/` concentra acesso assíncrono às tabelas principais.
- `docker-compose.yml` sobe `postgres`, `bot` e `api`.

O bot tenta usar Postgres no boot. Se `DATABASE_URL` estiver ausente ou o banco estiver indisponível, ele continua operando em modo legado com JSON.

## Operação Atual

No boot, o bot inicializa banco e config, carrega automaticamente todas as cogs com `setup()`, sincroniza slash commands e inicia o listener de `pg_notify` para recarga de cache. O estado atual é híbrido: parte da configuração já vem de `server_config`, `antispam_config` e `antinuke_config`, mas ainda existem IDs e defaults hardcoded em alguns fluxos.

## Funcionalidades

### Economia e progressão

- `FenrirCoins`, daily, streak e rankings.
- XP por mensagem, voz e aventuras.
- Multiplicadores premium, dobro de XP e bônus de guild.
- Loja com itens e cooldown por item.

### Guilds e aventuras

- Criação e gerenciamento de guilds.
- Banco, nível, XP, alianças e raids.
- Uma aventura ativa por usuário, com persistência em DB ou fallback JSON.

### Moderação e automação

- Antispam configurável.
- Antinuke configurável.
- Bloqueio de convites de outros servidores.
- Auto-remove de bots não autorizados.
- Tickets, entrada e utilidades de moderação.

### Integrações

- Riot Games API.
- Steam API.
- GNews.
- Mercado Pago para ativação de premium.

## Setup

1. Clone o repositório.

```bash
git clone https://github.com/dedez1nn/Fenrir-BOT-CODE.git
cd Fenrir-BOT-CODE
```

2. Instale as dependências.

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
```

3. Crie o `.env`.

```bash
cp .env.example .env
```

## Variáveis de ambiente

### Bot

- `TOKEN` — token do bot no Discord.
- `ACCESS_TOKEN` — access token do Mercado Pago.
- `GUILD_ID` — guild principal usada para carregar `server_config`.
- `LOG_LEVEL` — padrão `INFO`.
- `ENVIRONMENT` — padrão `development`.

### Banco

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`

### API admin

- `API_PORT` — padrão `8000`.
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI`
- `JWT_SECRET`
- `ADMIN_ROLE_IDS`
- `MP_WEBHOOK_SECRET`
- `CORS_ORIGINS`

### Integrações externas

- `RIOT_API_KEY`
- `RIOT_REGION`
- `STEAM_API_KEY`
- `GNEWS_API_KEY`

Veja `.env.example` para os valores padrão e comentários de cada campo.

## Execução

### Bot local

```bash
python main.py
```

### Stack completa com Docker

```bash
docker compose up --build
```

### Apenas Postgres para desenvolvimento local

```bash
docker compose up -d postgres
```

### Aplicar migrações e importar JSONs manualmente

```bash
python -m scripts.db_setup
python -m scripts.db_setup --no-import
```

## API administrativa

A API FastAPI expõe atualmente:

- `/health`
- `/auth/*`
- `/webhooks/mercadopago`
- `/config/{guild_id}`
- `/items`
- `/users`
- `/antispam/config/{guild_id}`
- `/antispam/audit/{guild_id}`
- `/antinuke/config/{guild_id}`

O bot e a API se comunicam pelo banco. Após mutações relevantes, a API usa `pg_notify('fenrir_cache', ...)` para invalidar cache no bot sem restart.

## Testes

```bash
pytest
pytest tests/test_aventura.py
pytest tests/test_aventura.py::TestAventuraCog::test_init
```

Estado verificado nesta base: `162 passed`, com warnings de compatibilidade e uso de `datetime.utcnow()`.

## Referências

- `MIGRATION.md` descreve a evolução da migração para PostgreSQL e API.
- `CLAUDE.md` documenta contratos técnicos e convenções para trabalhar no código.
