"""Endpoints para gerenciamento de feature flags por servidor (Phase 5-6, 11-12).

GET   /features/{guild_id}                      — lista todas as features com estado enabled
GET   /features/{guild_id}/validation           — roda validate_all contra server_config atual
PUT   /features/{guild_id}/{feature}            — habilita/desabilita feature + emite NOTIFY
PATCH /features/{guild_id}/{feature}/config     — salva config JSONB de uma feature
PUT   /features/{guild_id}/bulk                 — toggle múltiplas features em batch
"""

from __future__ import annotations

import json
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


class FeatureConfigPatch(BaseModel):
    config: Dict[str, Any]


class BulkFeatureItem(BaseModel):
    feature: str
    enabled: bool


class BulkFeatureToggle(BaseModel):
    features: List[BulkFeatureItem]


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
async def validate_features(
    guild_id: int,
    live: bool = False,
    _=Depends(require_admin),
) -> Dict[str, Any]:
    """Retorna o estado de validação de todas as features.

    Por padrão lê o último resultado persistido pelo bot (rápido).
    Com `?live=true` re-executa os validadores em tempo real contra server_config.
    """
    if live:
        async with api_db.acquire() as conn:
            cfg_row = await conn.fetchrow(
                "SELECT * FROM server_config WHERE guild_id = $1", guild_id
            )
        if cfg_row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="server_config não existe para esta guild",
            )
        from db.validators import validate_all
        all_errors = validate_all(dict(cfg_row))
        result: Dict[str, Any] = {}
        for feature, errors in all_errors.items():
            result[feature] = {"is_valid": len(errors) == 0, "errors": errors, "source": "live"}
        return {"guild_id": guild_id, "features": result}

    async with api_db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT feature, validation_errors FROM server_feature_config WHERE guild_id = $1",
            guild_id,
        )
    result = {}
    for row in rows:
        errors = row["validation_errors"] or []
        result[row["feature"]] = {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "source": "stored",
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


@router.patch("/{guild_id}/{feature}/config", response_model=Dict[str, Any])
async def patch_feature_config(
    guild_id: int,
    feature: str,
    body: FeatureConfigPatch,
    user=Depends(require_admin),
) -> Dict[str, Any]:
    """Salva a config JSONB de uma feature para a guild. Emite NOTIFY ao bot."""
    if feature not in _KNOWN_FEATURES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Feature desconhecida: '{feature}'. Válidas: {sorted(_KNOWN_FEATURES)}",
        )

    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO server_feature_config (guild_id, feature, config, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (guild_id, feature) DO UPDATE
                SET config = EXCLUDED.config, updated_at = NOW()
            RETURNING feature, enabled, config, updated_at
            """,
            guild_id,
            feature,
            json.dumps(body.config),
        )

    try:
        async with api_db.acquire() as conn2:
            await conn2.execute("SELECT pg_notify('fenrir_cache', $1)", f"feature:{guild_id}:{feature}")
            await write_audit(conn2, guild_id, user, "feature_config", body.config, target=feature)
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY/audit feature_config: %s", exc)

    return {
        "guild_id": guild_id,
        "feature": row["feature"],
        "enabled": row["enabled"],
        "config": row["config"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.put("/{guild_id}/bulk", response_model=Dict[str, Any])
async def bulk_toggle_features(
    guild_id: int,
    body: BulkFeatureToggle,
    user=Depends(require_admin),
) -> Dict[str, Any]:
    """Habilita/desabilita múltiplas features em uma única operação. Emite NOTIFY para cada uma."""
    unknown = {item.feature for item in body.features} - _KNOWN_FEATURES
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Features desconhecidas: {sorted(unknown)}",
        )

    results = []
    async with api_db.acquire() as conn:
        for item in body.features:
            row = await conn.fetchrow(
                """
                INSERT INTO server_feature_config (guild_id, feature, enabled, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (guild_id, feature) DO UPDATE
                    SET enabled = EXCLUDED.enabled, updated_at = NOW()
                RETURNING feature, enabled, updated_at
                """,
                guild_id,
                item.feature,
                item.enabled,
            )
            results.append({
                "feature": row["feature"],
                "enabled": row["enabled"],
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            })

    try:
        async with api_db.acquire() as conn2:
            for item in body.features:
                await conn2.execute(
                    "SELECT pg_notify('fenrir_cache', $1)", f"feature:{guild_id}:{item.feature}"
                )
            await write_audit(
                conn2, guild_id, user, "feature_bulk",
                {"features": [{"feature": i.feature, "enabled": i.enabled} for i in body.features]},
            )
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY/audit bulk features: %s", exc)

    return {"guild_id": guild_id, "results": results}
