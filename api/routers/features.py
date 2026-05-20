"""Endpoints para gerenciamento de feature flags por servidor (Phase 5-6).

GET  /features/{guild_id}              — lista todas as features com estado enabled
GET  /features/{guild_id}/validation   — roda validate_all contra server_config atual
PUT  /features/{guild_id}/{feature}    — habilita/desabilita feature + emite NOTIFY
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .. import db as api_db
from ..audit import write_audit
from .auth import require_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["features"])

_KNOWN_FEATURES = {
    "tickets", "voice_creator", "member_logs", "colors", "adventures",
    "guild_raids", "riot", "steam", "gnews", "antispam", "antinuke",
    "premium", "invite_blocker", "auto_remove_bots", "xp", "economy",
    "guilds", "status",
}


class FeatureToggle(BaseModel):
    enabled: bool


@router.get("/{guild_id}", response_model=Dict[str, Any])
async def list_features(guild_id: int, _=Depends(require_admin)) -> Dict[str, Any]:
    """Retorna todas as features configuradas para a guild, com estado enabled."""
    async with api_db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT feature, enabled, config, updated_at "
            "FROM server_feature_config WHERE guild_id = $1 ORDER BY feature",
            guild_id,
        )
    return {
        row["feature"]: {
            "enabled": row["enabled"],
            "config": row["config"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    }


@router.get("/{guild_id}/validation", response_model=Dict[str, Any])
async def validate_features(guild_id: int, _=Depends(require_admin)) -> Dict[str, Any]:
    """Roda todos os validadores contra a server_config atual e retorna erros por feature."""
    async with api_db.acquire() as conn:
        cfg_row = await conn.fetchrow(
            "SELECT * FROM server_config WHERE guild_id = $1", guild_id
        )
    if cfg_row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="server_config não existe para esta guild",
        )

    cfg = dict(cfg_row)

    from db.validators import validate_all
    all_errors = validate_all(cfg)

    result: Dict[str, Any] = {}
    for feature, errors in all_errors.items():
        result[feature] = {
            "is_valid": len(errors) == 0,
            "errors": errors,
        }
    return {"guild_id": guild_id, "features": result}


@router.put("/{guild_id}/{feature}", response_model=Dict[str, Any])
async def toggle_feature(
    guild_id: int,
    feature: str,
    body: FeatureToggle,
    user=Depends(require_admin),
) -> Dict[str, Any]:
    """Habilita ou desabilita uma feature para a guild. Emite NOTIFY ao bot."""
    if feature not in _KNOWN_FEATURES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Feature desconhecida: '{feature}'. Válidas: {sorted(_KNOWN_FEATURES)}",
        )

    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO server_feature_config (guild_id, feature, enabled, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (guild_id, feature) DO UPDATE
                SET enabled = EXCLUDED.enabled, updated_at = NOW()
            RETURNING feature, enabled, updated_at
            """,
            guild_id,
            feature,
            body.enabled,
        )

    try:
        async with api_db.acquire() as conn2:
            await conn2.execute("SELECT pg_notify('fenrir_cache', $1)", f"feature:{guild_id}:{feature}")
            await write_audit(conn2, guild_id, user, "feature", {"enabled": body.enabled}, target=feature)
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY/audit feature: %s", exc)

    return {
        "guild_id": guild_id,
        "feature": row["feature"],
        "enabled": row["enabled"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
