-- Fase 3: cria tabela premium_catalog substituindo os dicts hardcoded em pix.py.

CREATE TABLE IF NOT EXISTS premium_catalog (
    plan_key          TEXT           PRIMARY KEY,
    label             TEXT           NOT NULL,
    price_brl         NUMERIC(10, 2),
    duration_days     INT            NOT NULL DEFAULT 30,
    role_id           BIGINT,
    coins_reward      BIGINT         NOT NULL DEFAULT 0,
    xp_reward         BIGINT         NOT NULL DEFAULT 0,
    xp_multiplier     NUMERIC(4, 2)  NOT NULL DEFAULT 1.0,
    coins_multiplier  NUMERIC(4, 2)  NOT NULL DEFAULT 1.0,
    active            BOOLEAN        NOT NULL DEFAULT TRUE,

    CONSTRAINT premium_catalog_multiplier_chk CHECK (xp_multiplier >= 1.0 AND coins_multiplier >= 1.0)
);

INSERT INTO premium_catalog
    (plan_key, label, price_brl, duration_days, role_id, coins_reward, xp_reward, xp_multiplier, coins_multiplier, active)
VALUES
    ('aventureiro', 'Aventureiro',  3.99, 30, 1430230150359945306,  30000,  25000, 2.0, 2.0, TRUE),
    ('lendario',    'Lendário',     7.99, 30, 1429546091199729704,  60000,  50000, 4.0, 4.0, TRUE),
    ('mitico',      'Mítico',      13.99, 30, 1428728597501444186, 120000, 100000, 6.0, 6.0, TRUE)
ON CONFLICT (plan_key) DO NOTHING;
