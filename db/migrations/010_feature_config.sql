-- Fase 4: cria server_feature_config para feature flags por servidor.
-- Seed inicial com todas as features atualmente ativas (enabled = TRUE).

CREATE TABLE IF NOT EXISTS server_feature_config (
    guild_id    BIGINT      NOT NULL,
    feature     TEXT        NOT NULL,
    enabled     BOOLEAN     NOT NULL DEFAULT TRUE,
    config      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, feature)
);

CREATE INDEX IF NOT EXISTS sfc_guild_idx ON server_feature_config (guild_id);

-- Seed: todas as features já em produção começam habilitadas.
INSERT INTO server_feature_config (guild_id, feature, enabled) VALUES
    (1426202696955986022, 'tickets',          TRUE),
    (1426202696955986022, 'voice_creator',    TRUE),
    (1426202696955986022, 'member_logs',      TRUE),
    (1426202696955986022, 'colors',           TRUE),
    (1426202696955986022, 'adventures',       TRUE),
    (1426202696955986022, 'guild_raids',      TRUE),
    (1426202696955986022, 'riot',             TRUE),
    (1426202696955986022, 'steam',            TRUE),
    (1426202696955986022, 'gnews',            TRUE),
    (1426202696955986022, 'antispam',         TRUE),
    (1426202696955986022, 'antinuke',         TRUE),
    (1426202696955986022, 'premium',          TRUE),
    (1426202696955986022, 'invite_blocker',   TRUE),
    (1426202696955986022, 'auto_remove_bots', TRUE),
    (1426202696955986022, 'xp',               TRUE),
    (1426202696955986022, 'economy',          TRUE),
    (1426202696955986022, 'guilds',           TRUE),
    (1426202696955986022, 'status',           TRUE)
ON CONFLICT (guild_id, feature) DO NOTHING;
