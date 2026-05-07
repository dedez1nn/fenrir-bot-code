-- Fenrir — schema inicial (migração JSON → PostgreSQL)
-- Idempotente: pode rodar múltiplas vezes sem efeito colateral.

-- ─── server_config ─────────────────────────────────────────────────────────
-- Substitui todos os IDs hardcoded e parâmetros operacionais do bot.
CREATE TABLE IF NOT EXISTS server_config (
    guild_id                  BIGINT PRIMARY KEY,

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

    admin_ping_ids            BIGINT[] NOT NULL DEFAULT '{}',

    levelup_role_map          JSONB    NOT NULL DEFAULT '{}'::jsonb,

    premium_prices            JSONB    NOT NULL DEFAULT '{"aventureiro":0,"lendario":0,"mitico":0}'::jsonb,
    premium_duration_days     INT      NOT NULL DEFAULT 30,
    premium_multipliers       JSONB    NOT NULL DEFAULT '{"aventureiro":2,"lendario":4,"mitico":6}'::jsonb,

    daily_coins               BIGINT   NOT NULL DEFAULT 10000,
    daily_streak_bonus        BIGINT   NOT NULL DEFAULT 10000,
    coins_por_mensagem        BIGINT   NOT NULL DEFAULT 5000,
    coins_por_voz             BIGINT   NOT NULL DEFAULT 15000,
    xp_por_mensagem           BIGINT   NOT NULL DEFAULT 5000,
    xp_por_voz                BIGINT   NOT NULL DEFAULT 15000,
    voice_xp_interval_s       INT      NOT NULL DEFAULT 300,
    bonus_coins_por_nivel     BIGINT   NOT NULL DEFAULT 50000,

    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id          BIGINT PRIMARY KEY,
    xp               BIGINT      NOT NULL DEFAULT 0,
    nivel            INT         NOT NULL DEFAULT 1,
    titulo           TEXT,
    dobro            BOOLEAN     NOT NULL DEFAULT FALSE,
    dobro_expiracao  TIMESTAMPTZ,
    premium          TEXT,
    premium_expira   TIMESTAMPTZ,
    coins            BIGINT      NOT NULL DEFAULT 0,
    daily_streak     INT         NOT NULL DEFAULT 0,
    last_daily       TIMESTAMPTZ,
    total_ganho      BIGINT      NOT NULL DEFAULT 0,
    guild_name       TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT users_premium_chk CHECK (premium IS NULL OR premium IN ('aventureiro','lendario','mitico'))
);
CREATE INDEX IF NOT EXISTS users_nivel_idx   ON users (nivel DESC);
CREATE INDEX IF NOT EXISTS users_premium_idx ON users (premium) WHERE premium IS NOT NULL;
CREATE INDEX IF NOT EXISTS users_coins_idx   ON users (coins DESC);

-- ─── items (loja) ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS items (
    id           SERIAL PRIMARY KEY,
    nome         TEXT        NOT NULL,
    preco        BIGINT      NOT NULL,
    descricao    TEXT,
    cooldown_h   FLOAT       NOT NULL DEFAULT 0,
    criado_por   BIGINT      NOT NULL,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT items_preco_chk CHECK (preco >= 0)
);
CREATE INDEX IF NOT EXISTS items_preco_idx ON items (preco DESC);

-- ─── cooldowns ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cooldowns (
    user_id     BIGINT      NOT NULL,
    item_id     INT         NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
CREATE INDEX IF NOT EXISTS cooldowns_expires_idx ON cooldowns (expires_at);

-- ─── antispam_users ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS antispam_users (
    guild_id        BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    score           DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_event_ts   DOUBLE PRECISION NOT NULL DEFAULT 0,
    infractions     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    punishments     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    blacklisted     BOOLEAN     NOT NULL DEFAULT FALSE,
    recent_messages JSONB       NOT NULL DEFAULT '[]'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX IF NOT EXISTS antispam_users_score_idx ON antispam_users (guild_id, score DESC);

-- ─── antispam_whitelist ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS antispam_whitelist (
    guild_id  BIGINT NOT NULL,
    user_id   BIGINT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

-- ─── antispam_config ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS antispam_config (
    guild_id   BIGINT      PRIMARY KEY,
    config     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── antinuke_config ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS antinuke_config (
    guild_id   BIGINT      PRIMARY KEY,
    config     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    alert_only BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── antispam_audit ─────────────────────────────────────────────────────────
-- Trilha de eventos de moderação (entradas, punições, alertas) para o painel.
CREATE TABLE IF NOT EXISTS antispam_audit (
    id         BIGSERIAL PRIMARY KEY,
    guild_id   BIGINT      NOT NULL,
    user_id    BIGINT      NOT NULL,
    event      TEXT        NOT NULL,
    score      DOUBLE PRECISION,
    reason     TEXT,
    payload    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS antispam_audit_guild_user_idx ON antispam_audit (guild_id, user_id, created_at DESC);

-- ─── schema_migrations (controle de aplicação) ─────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
