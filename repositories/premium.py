"""Repositório para premium_catalog — planos premium do produto."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


async def get_all(pool) -> List[Dict[str, Any]]:
    """Retorna todos os planos ativos, ordenados por preço."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM premium_catalog WHERE active = TRUE ORDER BY price_brl ASC NULLS LAST"
        )
    return [dict(r) for r in rows]


async def get_plan(pool, plan_key: str) -> Optional[Dict[str, Any]]:
    """Retorna um plano pelo plan_key, ou None se não existir."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM premium_catalog WHERE plan_key = $1", plan_key
        )
    return dict(row) if row else None


async def upsert(
    pool,
    plan_key: str,
    label: str,
    price_brl: float,
    duration_days: int,
    role_id: Optional[int],
    coins_reward: int,
    xp_reward: int,
    xp_multiplier: float,
    coins_multiplier: float,
    active: bool = True,
) -> None:
    """Insere ou atualiza um plano premium."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO premium_catalog
                (plan_key, label, price_brl, duration_days, role_id,
                 coins_reward, xp_reward, xp_multiplier, coins_multiplier, active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (plan_key) DO UPDATE SET
                label            = EXCLUDED.label,
                price_brl        = EXCLUDED.price_brl,
                duration_days    = EXCLUDED.duration_days,
                role_id          = EXCLUDED.role_id,
                coins_reward     = EXCLUDED.coins_reward,
                xp_reward        = EXCLUDED.xp_reward,
                xp_multiplier    = EXCLUDED.xp_multiplier,
                coins_multiplier = EXCLUDED.coins_multiplier,
                active           = EXCLUDED.active
            """,
            plan_key, label, price_brl, duration_days, role_id,
            coins_reward, xp_reward, xp_multiplier, coins_multiplier, active,
        )
