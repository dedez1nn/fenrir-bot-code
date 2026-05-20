"""Endpoint unificado de servidor — Phase 7.

GET  /server/{guild_id}        — server_config + features com validação + premium catalog
GET  /server/{guild_id}/audit  — histórico paginado de alterações (Phase 9)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import db as api_db
from .auth import require_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/server", tags=["server"])


@router.get("/{guild_id}", response_model=Dict[str, Any])
async def get_server_dashboard(guild_id: int, _=Depends(require_admin)) -> Dict[str, Any]:
    """Retorna server_config + estado de features com erros de validação + catálogo premium.

    Projetado para ser a única chamada necessária para renderizar o painel de configuração.
    """
    async with api_db.acquire() as conn:
        cfg_row, feature_rows, catalog_rows = await _fetch_all(conn, guild_id)

    if cfg_row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="server_config não existe para esta guild",
        )

    cfg = dict(cfg_row)

    from db.validators import validate_all
    all_errors = validate_all(cfg)

    features: Dict[str, Any] = {}
    for row in feature_rows:
        fname = row["feature"]
        errors = all_errors.get(fname, [])
        features[fname] = {
            "enabled": row["enabled"],
            "config": row["config"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "validation": {
                "is_valid": len(errors) == 0,
                "errors": errors,
            },
        }

    # Features em VALIDATORS mas sem row em server_feature_config aparecem como enabled=True (fallback).
    for fname, errors in all_errors.items():
        if fname not in features:
            features[fname] = {
                "enabled": True,
                "config": {},
                "updated_at": None,
                "validation": {
                    "is_valid": len(errors) == 0,
                    "errors": errors,
                },
            }

    catalog = [dict(r) for r in catalog_rows]

    return {
        "guild_id": guild_id,
        "server_config": cfg,
        "features": features,
        "premium_catalog": catalog,
    }


@router.get("/{guild_id}/audit", response_model=Dict[str, Any])
async def get_audit_log(
    guild_id: int,
    page: int = Query(0, ge=0),
    per_page: int = Query(50, ge=1, le=200),
    kind: Optional[str] = Query(None, pattern="^(server_config|feature|global_config)$"),
    _=Depends(require_admin),
) -> Dict[str, Any]:
    """Histórico paginado de alterações de configuração."""
    offset = page * per_page

    where = "WHERE guild_id = $1"
    params: list = [guild_id]
    if kind:
        params.append(kind)
        where += f" AND kind = ${len(params)}"

    try:
        async with api_db.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM config_audit_log {where} ORDER BY changed_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}",
                *params,
                per_page,
                offset,
            )
    except Exception as exc:
        log.warning("Falha ao ler config_audit_log: %s", exc)
        return {"guild_id": guild_id, "page": page, "entries": []}

    entries = [
        {
            "id": row["id"],
            "changed_by": row["changed_by"],
            "kind": row["kind"],
            "target": row["target"],
            "patch": row["patch"],
            "changed_at": row["changed_at"].isoformat() if row["changed_at"] else None,
        }
        for row in rows
    ]
    return {"guild_id": guild_id, "page": page, "entries": entries}


async def _fetch_all(conn, guild_id: int):
    cfg_row = await conn.fetchrow("SELECT * FROM server_config WHERE guild_id = $1", guild_id)
    feature_rows = await conn.fetch(
        "SELECT feature, enabled, config, updated_at FROM server_feature_config WHERE guild_id = $1 ORDER BY feature",
        guild_id,
    )
    catalog_rows = await conn.fetch(
        "SELECT * FROM premium_catalog WHERE active = TRUE ORDER BY price_brl ASC"
    )
    return cfg_row, feature_rows, catalog_rows
