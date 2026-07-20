-- Copa 2026 encerrada — remove a coluna de canal de notificações da Copa.
-- selfbot_trap_channel_id / selfbot_log_channel_id / fenrir_command_channel_id
-- (criadas na mesma migration 014) continuam em uso e não são afetadas.

ALTER TABLE server_config
    DROP COLUMN IF EXISTS copa_notify_channel_id;
