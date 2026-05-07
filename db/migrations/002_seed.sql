-- Seed inicial: registra a guild atual (Alcateia do Fenrir) com os IDs
-- atualmente hardcoded no código. Idempotente: ON CONFLICT DO NOTHING.

INSERT INTO server_config (
    guild_id,
    commands_channel_id,
    status_channel_id,
    afk_voice_channel_id,
    colors_channel_id,
    pix_channel_id,
    tickets_channel_id,
    antispam_log_channel_id,
    antinuke_log_channel_id,
    coins_log_channel_id,
    xp_log_channel_id,
    levelup_channel_id,
    levelup_role_map,
    premium_prices,
    premium_multipliers
) VALUES (
    1426202696955986022,
    1426205118293868748,
    1427050535634075851,
    1427320869016829952,
    1428161467286421524,
    1429555260917284947,
    1426275563378839606,
    NULL,
    NULL,
    1427483403510354035,
    1427479688544129064,
    1427310936263364690,
    '{"2":1427356351516119180,"5":1427318172033351781,"10":1427318241197293711,"20":1427318396772417701,"30":1427318764814336213,"40":1427319349764423771,"50":1427319515548483757}'::jsonb,
    '{"aventureiro":0,"lendario":0,"mitico":0}'::jsonb,
    '{"aventureiro":2,"lendario":4,"mitico":6}'::jsonb
)
ON CONFLICT (guild_id) DO NOTHING;
