"""Repositório para a tabela `users` (Phase 4).

Todas as funções de escrita usam SQL atômico (INSERT … ON CONFLICT DO UPDATE ou
UPDATE … RETURNING), eliminando a race condition do modo JSON onde dois cogs
gravavam o mesmo arquivo com snapshots diferentes da memória.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ─── helpers ──────────────────────────────────────────────────────────────────


async def _ensure(conn, user_id: int) -> None:
    """Cria o row do usuário com defaults se ainda não existir."""
    await conn.execute(
        "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id
    )


def row_to_cache(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converte um row do asyncpg para o formato do dict em memória usado pelos cogs."""
    last_daily = row.get("last_daily")
    dobro_exp = row.get("dobro_expiracao")
    return {
        "xp": int(row.get("xp") or 0),
        "nivel": int(row.get("nivel") or 1),
        "titulo": row.get("titulo") or "Aprendiz",
        "dobro": bool(row.get("dobro", False)),
        "dobro_expiracao": dobro_exp.timestamp() if isinstance(dobro_exp, datetime) else dobro_exp,
        "premium": row.get("premium"),
        "coins": int(row.get("coins") or 0),
        "daily_streak": int(row.get("daily_streak") or 0),
        "last_daily": last_daily.timestamp() if isinstance(last_daily, datetime) else last_daily,
        "total_ganho": int(row.get("total_ganho") or 0),
        "guild": row.get("guild_name"),
    }


# ─── leituras ─────────────────────────────────────────────────────────────────


async def get(pool, user_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(row) if row else None


async def get_or_create(pool, user_id: int) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO users (user_id) VALUES ($1) "
            "ON CONFLICT (user_id) DO NOTHING RETURNING *",
            user_id,
        )
        if row:
            return dict(row)
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(row) if row else {"user_id": user_id}


async def get_all(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
    return [dict(r) for r in rows]


async def get_ranking_coins(pool, limit: int = 50) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY coins DESC LIMIT $1", limit
        )
    return [dict(r) for r in rows]


async def get_ranking_xp(pool, limit: int = 50) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY nivel DESC, xp DESC LIMIT $1", limit
        )
    return [dict(r) for r in rows]


# ─── coins ────────────────────────────────────────────────────────────────────


async def add_coins(pool, user_id: int, amount: int) -> Dict[str, Any]:
    """Adiciona `amount` coins atomicamente. Cria o row se não existir. Retorna o row atualizado."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (user_id, coins, total_ganho)
            VALUES ($1, $2, $2)
            ON CONFLICT (user_id) DO UPDATE SET
                coins       = users.coins + EXCLUDED.coins,
                total_ganho = users.total_ganho + EXCLUDED.total_ganho,
                updated_at  = NOW()
            RETURNING *
            """,
            user_id,
            int(amount),
        )
    return dict(row)


async def remove_coins(pool, user_id: int, amount: int) -> Dict[str, Any]:
    """Remove `amount` coins (mínimo 0). Cria o row se não existir. Retorna o row atualizado."""
    async with pool.acquire() as conn:
        await _ensure(conn, user_id)
        row = await conn.fetchrow(
            """
            UPDATE users
            SET coins = GREATEST(0, coins - $2), updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            int(amount),
        )
    return dict(row)


async def transfer(
    pool, sender_id: int, receiver_id: int, amount: int
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Transferência atômica via transação. Lança ValueError('insufficient_funds') se saldo insuficiente."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            bal = await conn.fetchval(
                "SELECT coins FROM users WHERE user_id = $1 FOR UPDATE", sender_id
            )
            if bal is None or bal < amount:
                raise ValueError("insufficient_funds")
            s_row = await conn.fetchrow(
                "UPDATE users SET coins = coins - $2, updated_at = NOW() "
                "WHERE user_id = $1 RETURNING *",
                sender_id,
                amount,
            )
            await _ensure(conn, receiver_id)
            r_row = await conn.fetchrow(
                """
                UPDATE users
                SET coins = coins + $2, total_ganho = total_ganho + $2, updated_at = NOW()
                WHERE user_id = $1 RETURNING *
                """,
                receiver_id,
                amount,
            )
    return dict(s_row), dict(r_row)


async def update_daily(
    pool, user_id: int, coins_add: int, new_streak: int, now: datetime
) -> Dict[str, Any]:
    """Atualiza daily de forma atômica: adiciona coins, seta streak e last_daily."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (user_id, coins, total_ganho, daily_streak, last_daily)
            VALUES ($1, $2, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                coins        = users.coins + EXCLUDED.coins,
                total_ganho  = users.total_ganho + EXCLUDED.total_ganho,
                daily_streak = $3,
                last_daily   = $4,
                updated_at   = NOW()
            RETURNING *
            """,
            user_id,
            int(coins_add),
            new_streak,
            now,
        )
    return dict(row)


# ─── xp / nível ───────────────────────────────────────────────────────────────


async def update_xp_nivel(pool, user_id: int, xp: int, nivel: int) -> Dict[str, Any]:
    """Persiste xp e nivel atomicamente. Não toca em coins."""
    async with pool.acquire() as conn:
        await _ensure(conn, user_id)
        row = await conn.fetchrow(
            """
            UPDATE users
            SET xp = $2, nivel = $3, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            int(xp),
            int(nivel),
        )
    return dict(row)


async def reset_xp_one(pool, user_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET xp = 0, nivel = 1, updated_at = NOW() WHERE user_id = $1",
            user_id,
        )


async def reset_xp_all(pool) -> int:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET xp = 0, nivel = 1, updated_at = NOW()"
        )
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


# ─── perfil ───────────────────────────────────────────────────────────────────


async def set_titulo(pool, user_id: int, titulo: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, titulo) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET titulo = EXCLUDED.titulo, updated_at = NOW()",
            user_id,
            titulo,
        )


async def set_premium(
    pool,
    user_id: int,
    premium: Optional[str],
    expira: Optional[datetime],
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, premium, premium_expira) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "premium = EXCLUDED.premium, premium_expira = EXCLUDED.premium_expira, updated_at = NOW()",
            user_id,
            premium,
            expira,
        )


async def set_dobro(
    pool,
    user_id: int,
    dobro: bool,
    dobro_expiracao: Optional[datetime],
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, dobro, dobro_expiracao) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "dobro = EXCLUDED.dobro, dobro_expiracao = EXCLUDED.dobro_expiracao, updated_at = NOW()",
            user_id,
            dobro,
            dobro_expiracao,
        )


async def remove_xp(pool, user_id: int, amount: int) -> bool:
    """Subtrai `amount` de XP atomicamente se o usuário tiver saldo suficiente.

    Retorna True se a operação foi realizada, False se XP insuficiente.
    Não altera o nível — usado apenas em doações de raid (guild_2.py).
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET xp = xp - $2, updated_at = NOW() WHERE user_id = $1 AND xp >= $2",
            user_id,
            amount,
        )
    return result != "UPDATE 0"
