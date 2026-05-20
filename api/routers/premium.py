"""Endpoints para leitura e escrita do catálogo de planos premium."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, condecimal, field_validator

from ..db import acquire
from .auth import require_admin

router = APIRouter(prefix="/premium", tags=["premium"])


class PlanBody(BaseModel):
    label: str
    price_brl: Optional[float] = None
    duration_days: int = 30
    role_id: Optional[int] = None
    coins_reward: int = 0
    xp_reward: int = 0
    xp_multiplier: float = 1.0
    coins_multiplier: float = 1.0
    active: bool = True

    @field_validator("xp_multiplier", "coins_multiplier")
    @classmethod
    def multiplier_ge_1(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("multiplicador deve ser >= 1.0")
        return v


@router.get("/catalog", summary="Lista planos premium ativos")
async def list_catalog() -> List[Dict[str, Any]]:
    try:
        async with acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM premium_catalog WHERE active = TRUE ORDER BY price_brl ASC NULLS LAST"
            )
        return [dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.put("/catalog/{plan_key}", summary="Cria ou atualiza um plano premium")
async def upsert_plan(
    plan_key: str,
    body: PlanBody,
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        async with acquire() as conn:
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
                plan_key,
                body.label,
                body.price_brl,
                body.duration_days,
                body.role_id,
                body.coins_reward,
                body.xp_reward,
                body.xp_multiplier,
                body.coins_multiplier,
                body.active,
            )
            row = await conn.fetchrow(
                "SELECT * FROM premium_catalog WHERE plan_key = $1", plan_key
            )
        return dict(row)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
