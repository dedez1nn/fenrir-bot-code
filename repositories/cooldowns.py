"""Repositório para a tabela `cooldowns`."""

from __future__ import annotations

from datetime import datetime


async def register(pool, user_id: int, item_id: int, expires_at: datetime) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO cooldowns (user_id, item_id, expires_at) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id, item_id) DO UPDATE SET expires_at = EXCLUDED.expires_at",
            user_id,
            item_id,
            expires_at,
        )


async def is_active(pool, user_id: int, item_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM cooldowns "
            "WHERE user_id = $1 AND item_id = $2 AND expires_at > NOW()",
            user_id,
            item_id,
        )
    return row is not None


async def remaining_seconds(pool, user_id: int, item_id: int) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT EXTRACT(EPOCH FROM (expires_at - NOW())) AS secs "
            "FROM cooldowns WHERE user_id = $1 AND item_id = $2 AND expires_at > NOW()",
            user_id,
            item_id,
        )
    return max(0.0, float(row["secs"])) if row else 0.0


async def cleanup_expired(pool) -> int:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM cooldowns WHERE expires_at <= NOW()")
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0
