-- Phase 6: guilds + aventuras → PostgreSQL

CREATE TABLE IF NOT EXISTS guilds (
    guild_id     TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    lider        BIGINT NOT NULL,
    banco        BIGINT NOT NULL DEFAULT 0,
    nivel        INT NOT NULL DEFAULT 1,
    xp           BIGINT NOT NULL DEFAULT 0,
    motto        TEXT NOT NULL DEFAULT '',
    emoji        TEXT NOT NULL DEFAULT '',
    data_criacao DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),
    ultima_raid  DOUBLE PRECISION NOT NULL DEFAULT 0,
    data_alianca DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS guilds_nome_idx  ON guilds (lower(nome));
CREATE INDEX IF NOT EXISTS guilds_nivel_idx ON guilds (nivel DESC, xp DESC);

-- Members (cargo ∈ {'Líder','Admin','Membro'})
CREATE TABLE IF NOT EXISTS guild_members (
    guild_id   TEXT    NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id    BIGINT  NOT NULL,
    cargo      TEXT    NOT NULL DEFAULT 'Membro',
    entrada    DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),
    ativo      BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (guild_id, user_id),
    CONSTRAINT guild_members_cargo_chk CHECK (cargo IN ('Líder', 'Admin', 'Membro'))
);
CREATE INDEX IF NOT EXISTS guild_members_user_idx ON guild_members (user_id);

-- Pending invites (expire_at is a unix timestamp)
CREATE TABLE IF NOT EXISTS guild_invites (
    invite_id  TEXT   PRIMARY KEY,
    guild_id   TEXT   NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    usuario    BIGINT NOT NULL,
    criador    BIGINT NOT NULL,
    data       DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),
    expiracao  DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS guild_invites_usuario_idx ON guild_invites (usuario, expiracao);

-- Alliances: both (A,B) and (B,A) are stored for O(1) lookup
CREATE TABLE IF NOT EXISTS guild_alliances (
    guild_id   TEXT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    ally_id    TEXT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (guild_id, ally_id)
);

-- Active raids (complex transient state stored as JSONB)
CREATE TABLE IF NOT EXISTS guild_raids (
    raid_id    TEXT  PRIMARY KEY,
    data       JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One active adventure per player
CREATE TABLE IF NOT EXISTS adventures (
    user_id    BIGINT  PRIMARY KEY,
    inicio     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    canal_id   BIGINT,
    situacao   JSONB   NOT NULL DEFAULT '{}',
    notificado BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
