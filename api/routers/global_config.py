"""Endpoints para leitura e escrita de global_config (dono do bot)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from ..audit import write_audit
from ..db import acquire
from .auth import require_admin

router = APIRouter(prefix="/global-config", tags=["global-config"])


@router.get("", summary="Retorna todos os parâmetros globais")
async def list_global_config(
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        async with acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM global_config ORDER BY key")
        return {row["key"]: row["value"] for row in rows}
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.patch("/{key}", summary="Atualiza um parâmetro global")
async def update_global_config(
    key: str,
    body: Dict[str, Any],
    user: dict = Depends(require_admin),
) -> Dict[str, Any]:
    value = body.get("value")
    if value is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Campo 'value' obrigatório")
    try:
        async with acquire() as conn:
            await conn.execute(
                """
                INSERT INTO global_config (key, value, updated_at)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                key,
                __import__("json").dumps(value),
            )
            row = await conn.fetchrow("SELECT key, value FROM global_config WHERE key = $1", key)
            await write_audit(conn, 0, user, "global_config", {"key": key, "value": value})
        return {"key": row["key"], "value": row["value"]}
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
