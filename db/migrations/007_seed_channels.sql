-- Fase 2 seed: popula as novas colunas de canais/cargos para a guild principal.
-- IDs extraídos dos hardcodes removidos nas cogs.

UPDATE server_config SET
    member_join_log_channel_id  = 1426206240467320983,
    help_channel_id             = 1426274988046155787,
    member_leave_log_channel_id = 1427472688665854133,

    ticket_support_category_id  = 1426304224429608990,
    ticket_donation_category_id = 1426306944204804146,
    ticket_staff_role_ids       = ARRAY[1426202850769244301, 1426203167049121894]::BIGINT[],
    ticket_log_channel_id       = 1426323866963410985,

    voice_creator_channel_id    = 1429479982014660712,

    status_changelog_channel_id = 1427311999381147708,

    adventure_log_channel_id    = 1428872885216481432,

    guild_raid_channel_id       = 1430607187193102456,

    free_color_role_ids         = ARRAY[
        1428066709356548217, 1428066760141045771, 1428066489419825325,
        1428066484889849896, 1428066757322473588
    ]::BIGINT[],

    premium_color_role_ids      = ARRAY[
        1428400034952515696, 1428400132272951358,
        1428399718945390764, 1428399137057013783
    ]::BIGINT[],

    special_access_role_ids     = ARRAY[1428715049928757318]::BIGINT[]

WHERE guild_id = 1426202696955986022;
