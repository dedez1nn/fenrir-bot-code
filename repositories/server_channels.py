"""Repositório para os channel IDs de selfbot trap / canal-fenrir.

Substitui a antiga camada Mongo (`services/db.py`) — todos os campos vivem em
colunas de `server_config`. Usa `INSERT ... ON CONFLICT DO UPDATE` para que uma
guild sem row prévia em `server_config` ainda possa configurar esses canais
isoladamente (mesmo comportamento de upsert que o Mongo tinha).
"""

from __future__ import annotations


async def _get_channel(pool, guild_id: int, column: str) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {column} FROM server_config WHERE guild_id = $1", guild_id
        )
    return row[column] if row else None


async def _set_channel(pool, guild_id: int, column: str, channel_id: int | None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            f"INSERT INTO server_config (guild_id, {column}) VALUES ($1, $2) "
            f"ON CONFLICT (guild_id) DO UPDATE SET {column} = EXCLUDED.{column}, updated_at = NOW()",
            guild_id,
            channel_id,
        )


async def _get_all_channels(pool, column: str) -> dict[int, int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT guild_id, {column} FROM server_config WHERE {column} IS NOT NULL"
        )
    return {row["guild_id"]: row[column] for row in rows}


# ── Selfbot trap channels ─────────────────────────────────────────────────────

async def get_selfbot_channel(pool, guild_id: int) -> int | None:
    return await _get_channel(pool, guild_id, "selfbot_trap_channel_id")


async def set_selfbot_channel(pool, guild_id: int, channel_id: int) -> None:
    await _set_channel(pool, guild_id, "selfbot_trap_channel_id", channel_id)


async def remove_selfbot_channel(pool, guild_id: int) -> None:
    await _set_channel(pool, guild_id, "selfbot_trap_channel_id", None)


async def get_all_selfbot_channels(pool) -> dict[int, int]:
    return await _get_all_channels(pool, "selfbot_trap_channel_id")


# ── Selfbot log channels ──────────────────────────────────────────────────────

async def get_selfbot_log_channel(pool, guild_id: int) -> int | None:
    return await _get_channel(pool, guild_id, "selfbot_log_channel_id")


async def set_selfbot_log_channel(pool, guild_id: int, channel_id: int) -> None:
    await _set_channel(pool, guild_id, "selfbot_log_channel_id", channel_id)


async def remove_selfbot_log_channel(pool, guild_id: int) -> None:
    await _set_channel(pool, guild_id, "selfbot_log_channel_id", None)


async def get_all_selfbot_log_channels(pool) -> dict[int, int]:
    return await _get_all_channels(pool, "selfbot_log_channel_id")


# ── Command channels (canal-fenrir) ──────────────────────────────────────────

async def get_command_channel(pool, guild_id: int) -> int | None:
    return await _get_channel(pool, guild_id, "fenrir_command_channel_id")


async def set_command_channel(pool, guild_id: int, channel_id: int) -> None:
    await _set_channel(pool, guild_id, "fenrir_command_channel_id", channel_id)


async def remove_command_channel(pool, guild_id: int) -> None:
    await _set_channel(pool, guild_id, "fenrir_command_channel_id", None)


async def get_all_command_channels(pool) -> dict[int, int]:
    return await _get_all_channels(pool, "fenrir_command_channel_id")
