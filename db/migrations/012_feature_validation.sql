-- Fase 13: adiciona validation_errors JSONB à server_feature_config
-- para persistir o resultado da última validação de cada feature.

ALTER TABLE server_feature_config
    ADD COLUMN IF NOT EXISTS validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb;
