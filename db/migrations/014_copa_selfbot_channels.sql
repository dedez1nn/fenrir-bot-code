-- Migra os canais das cogs da Copa 2026 (copa/selfbot trap/canal-fenrir) do
-- MongoDB (services/db.py) para server_config, seguindo o mesmo padrão das
-- demais colunas de canal. Elimina a dependência de um segundo banco de dados
-- para um punhado de channel IDs por guild.

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS copa_notify_channel_id      BIGINT,
    ADD COLUMN IF NOT EXISTS selfbot_trap_channel_id     BIGINT,
    ADD COLUMN IF NOT EXISTS selfbot_log_channel_id      BIGINT,
    ADD COLUMN IF NOT EXISTS fenrir_command_channel_id   BIGINT;
