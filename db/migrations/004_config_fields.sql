-- Fase 0: adiciona colunas de configuração ausentes em server_config.
-- Elimina defaults divergentes entre xp.py e fenrir_coins.py.

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS xp_por_vitoria          BIGINT NOT NULL DEFAULT 10000,
    ADD COLUMN IF NOT EXISTS coins_por_vitoria        BIGINT NOT NULL DEFAULT 20000,
    ADD COLUMN IF NOT EXISTS xp_message_cooldown_s    INT    NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS coins_message_cooldown_s INT    NOT NULL DEFAULT 180;
