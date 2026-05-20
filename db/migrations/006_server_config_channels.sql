-- Fase 2: adiciona colunas de canais e cargos que estavam hardcoded nas cogs.

ALTER TABLE server_config
    -- MemberLogs
    ADD COLUMN IF NOT EXISTS member_join_log_channel_id   BIGINT,
    ADD COLUMN IF NOT EXISTS help_channel_id              BIGINT,
    ADD COLUMN IF NOT EXISTS member_leave_log_channel_id  BIGINT,

    -- TicketCog
    ADD COLUMN IF NOT EXISTS ticket_support_category_id   BIGINT,
    ADD COLUMN IF NOT EXISTS ticket_donation_category_id  BIGINT,
    ADD COLUMN IF NOT EXISTS ticket_staff_role_ids        BIGINT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS ticket_log_channel_id        BIGINT,

    -- VoiceCreator
    ADD COLUMN IF NOT EXISTS voice_creator_channel_id     BIGINT,

    -- StatusCog
    ADD COLUMN IF NOT EXISTS status_changelog_channel_id  BIGINT,

    -- AventuraCog
    ADD COLUMN IF NOT EXISTS adventure_log_channel_id     BIGINT,

    -- GuildAllianceRaidSystem
    ADD COLUMN IF NOT EXISTS guild_raid_channel_id        BIGINT,

    -- EnviarCores / CompraCog
    ADD COLUMN IF NOT EXISTS free_color_role_ids          BIGINT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS premium_color_role_ids       BIGINT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS special_access_role_ids      BIGINT[] NOT NULL DEFAULT '{}';
