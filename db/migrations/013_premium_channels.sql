-- Move os IDs hardcoded restantes (categoria de pagamento do Pix e canal de log
-- de expiração de premium) para server_config, seguindo o padrão da Fase 2.
-- IDs extraídos dos hardcodes removidos em pix.py e premium_manual.py.

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS premium_payment_category_id  BIGINT,
    ADD COLUMN IF NOT EXISTS premium_log_channel_id       BIGINT;

UPDATE server_config SET
    premium_payment_category_id = 1430229807450558504,
    premium_log_channel_id      = 1429919086934097950
WHERE guild_id = 1426202696955986022;
