-- Fase 1: cria tabela global_config para parâmetros do produto (dono do bot).
-- Separa configuração global de configuração por servidor.

CREATE TABLE IF NOT EXISTS global_config (
    key        TEXT        PRIMARY KEY,
    value      JSONB       NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO global_config (key, value) VALUES
    ('primary_guild_id',              'null'),
    ('server_config_ttl_s',           '300'),
    ('admin_session_ttl_h',           '12'),
    ('db_pool_min',                   '2'),
    ('db_pool_max',                   '10'),
    ('content_policy_blocked_terms',  '["admin","mod","staff","don","owner","@","#","http","discord.gg"]')
ON CONFLICT (key) DO NOTHING;
