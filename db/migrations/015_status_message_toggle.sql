-- Torna o envio do embed de status (postado em on_ready) opcional, desabilitado
-- por padrão. Admin liga/desliga via `!status-mensagem on|off`.

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS status_message_enabled BOOLEAN NOT NULL DEFAULT FALSE;
