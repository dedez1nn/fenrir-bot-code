-- Proteções opcionais contra farm passivo de XP.
-- Todas desligadas/neutras por padrão, exceto voice_xp_require_undeafened
-- (liga por padrão pois cobre diretamente o exploit de farm de voz AFK).

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS voice_xp_require_undeafened BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS voice_xp_min_members        INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS xp_message_min_chars        INTEGER NOT NULL DEFAULT 0;
