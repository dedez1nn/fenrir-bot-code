-- Fase 3: adiciona colunas de regras operacionais de guild e aventura.

ALTER TABLE server_config
    ADD COLUMN IF NOT EXISTS guild_xp_base         BIGINT NOT NULL DEFAULT 500000,
    ADD COLUMN IF NOT EXISTS guild_level_rewards    JSONB  NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS guild_raid_cooldown_s  INT    NOT NULL DEFAULT 86400,
    ADD COLUMN IF NOT EXISTS adventure_chances      JSONB  NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS adventure_rewards      JSONB  NOT NULL DEFAULT '{}'::jsonb;

-- Seed: preenche os valores atualmente hardcoded em guild.py e aventurar.py.
UPDATE server_config SET
    guild_level_rewards = '{
        "1":  {"banco": 0,       "vantagens": "Guild básica"},
        "2":  {"banco": 10000,   "vantagens": "+1 slot de admin"},
        "3":  {"banco": 25000,   "vantagens": "Multiplicador +0.1x"},
        "4":  {"banco": 50000,   "vantagens": "+5 slots de membros"},
        "5":  {"banco": 100000,  "vantagens": "Multiplicador +0.2x"},
        "6":  {"banco": 200000,  "vantagens": "+10 slots de membros"},
        "7":  {"banco": 350000,  "vantagens": "Multiplicador +0.3x"},
        "8":  {"banco": 500000,  "vantagens": "+15 slots de membros"},
        "9":  {"banco": 750000,  "vantagens": "Multiplicador +0.5x"},
        "10": {"banco": 1000000, "vantagens": "Título Lendário"},
        "11": {"banco": 1500000, "vantagens": "Multiplicador +0.7x"},
        "12": {"banco": 2000000, "vantagens": "+20 slots de membros"},
        "13": {"banco": 3000000, "vantagens": "Multiplicador +1.0x"},
        "14": {"banco": 4000000, "vantagens": "+25 slots de membros"},
        "15": {"banco": 5000000, "vantagens": "Título Mítico"}
    }'::jsonb,

    adventure_chances = '{
        "vitoria_combate_min": 30,
        "vitoria_combate_max": 50,
        "machucado_vitoria_min": 40,
        "machucado_vitoria_max": 60,
        "chance_furtividade": 50
    }'::jsonb,

    adventure_rewards = '{
        "penalidade_furtividade_min": 750,
        "penalidade_furtividade_max": 1500,
        "recompensa_furtividade_min": 1000,
        "recompensa_furtividade_max": 2000,
        "recompensa_tesouro_min": 1000,
        "recompensa_tesouro_max": 3000,
        "recompensa_vitoria_ileso_min": 800,
        "recompensa_vitoria_ileso_max": 1500,
        "recompensa_vitoria_machucado_min": 400,
        "recompensa_vitoria_machucado_max": 750,
        "xp_vitoria_ileso": 3000,
        "xp_vitoria_machucado": 1500,
        "xp_tesouro": 4000,
        "xp_furtividade": 2000
    }'::jsonb

WHERE guild_id = 1426202696955986022;
