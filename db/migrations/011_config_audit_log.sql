-- Phase 9: tabela de auditoria de alterações de configuração.
-- Registra quem alterou o quê e quando via API.

CREATE TABLE IF NOT EXISTS config_audit_log (
    id          BIGSERIAL    PRIMARY KEY,
    guild_id    BIGINT       NOT NULL,
    changed_by  TEXT         NOT NULL,   -- Discord user ID (JWT sub) ou 'dev' em modo dev
    kind        TEXT         NOT NULL,   -- 'server_config' | 'feature' | 'global_config'
    target      TEXT,                    -- feature name, config key, etc.
    patch       JSONB        NOT NULL DEFAULT '{}',
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cal_guild_idx ON config_audit_log (guild_id);
CREATE INDEX IF NOT EXISTS cal_time_idx  ON config_audit_log (changed_at DESC);
