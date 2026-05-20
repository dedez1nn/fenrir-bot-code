"""Endpoints de leitura/escrita de `users` (Phase 4).

Suporte a listagem paginada, consulta individual e atualização de premium.
Auth Discord OAuth2 será plugada na Fase 5 via `Depends(require_admin)`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from .. import db as api_db
from .auth import require_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_VALID_PLANS = {"aventureiro", "lendario", "mitico"}


class PremiumUpdate(BaseModel):
    premium: Optional[str] = None
    premium_expira: Optional[datetime] = None

    @field_validator("premium")
    @classmethod
    def validate_plan(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_PLANS:
            raise ValueError(f"Plano inválido. Use: {sorted(_VALID_PLANS)} ou null para remover.")
        return v


@router.get("", response_model=List[Dict[str, Any]])
async def list_users(
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=200),
    order_by: str = Query("coins", pattern="^(coins|nivel|xp|daily_streak)$"),
) -> List[Dict[str, Any]]:
    """Lista usuários com paginação. Ordenação por `coins` (padrão), `nivel`, `xp` ou `daily_streak`."""
    offset = page * per_page
    async with api_db.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM users ORDER BY {order_by} DESC LIMIT $1 OFFSET $2",
            per_page,
            offset,
        )
    return [dict(r) for r in rows]


@router.get("/{user_id}")
async def get_user(user_id: int) -> Dict[str, Any]:
    """Retorna dados completos de um usuário."""
    async with api_db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return dict(row)


@router.patch("/{user_id}/premium")
async def update_premium(user_id: int, body: PremiumUpdate, _=Depends(require_admin)) -> Dict[str, Any]:
    """Atualiza o plano premium de um usuário. Envie `premium: null` para remover."""
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET premium = $2, premium_expira = $3, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            body.premium,
            body.premium_expira,
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    try:
        async with api_db.acquire() as notify_conn:
            await notify_conn.execute(
                "SELECT pg_notify('fenrir_cache', $1)",
                f"user:{user_id}",
            )
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY user: %s", exc)

    return dict(row)
