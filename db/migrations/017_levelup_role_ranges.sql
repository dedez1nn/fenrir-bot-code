-- Migra levelup_role_map do formato antigo {"nivel": cargo_id} para uma
-- lista de faixas [{"cargo_id":..,"min":..,"max":..}], permitindo configurar
-- o intervalo de níveis de cada cargo (antes só um nível mínimo) via comando
-- !add-cargo-nivel / !remover-cargo-nivel / !listar-cargos-nivel.
ALTER TABLE server_config
    ALTER COLUMN levelup_role_map SET DEFAULT '[]'::jsonb;

DO $$
DECLARE
    r RECORD;
    keys int[];
    resultado jsonb;
    k int;
    idx int;
    nmax int;
BEGIN
    FOR r IN SELECT guild_id, levelup_role_map FROM server_config WHERE jsonb_typeof(levelup_role_map) = 'object' LOOP
        SELECT array_agg((key)::int ORDER BY (key)::int)
          INTO keys
          FROM jsonb_object_keys(r.levelup_role_map) AS key;

        resultado := '[]'::jsonb;
        IF keys IS NOT NULL THEN
            FOR idx IN 1 .. array_length(keys, 1) LOOP
                k := keys[idx];
                IF idx < array_length(keys, 1) THEN
                    nmax := keys[idx + 1] - 1;
                ELSE
                    nmax := NULL;
                END IF;
                resultado := resultado || jsonb_build_array(jsonb_build_object(
                    'cargo_id', (r.levelup_role_map ->> k::text)::bigint,
                    'min', k,
                    'max', nmax
                ));
            END LOOP;
        END IF;

        UPDATE server_config SET levelup_role_map = resultado WHERE guild_id = r.guild_id;
    END LOOP;
END $$;
