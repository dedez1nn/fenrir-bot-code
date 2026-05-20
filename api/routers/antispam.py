"""Endpoints de configuração e auditoria do antispam — Phase 5.

Todos os endpoints requerem autenticação de administrador.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import db as api_db
from ..audit import write_audit
from .auth import require_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/antispam", tags=["antispam"])


# ─── config ──────────────────────────────────────────────────────────────────

@router.get("/config/{guild_id}", dependencies=[Depends(require_admin)])
async def get_antispam_config(guild_id: int) -> Dict[str, Any]:
    """Retorna a configuração atual do antispam para a guild."""
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM antispam_config WHERE guild_id = $1", guild_id
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Configuração não encontrada")
    return dict(row)


@router.patch("/config/{guild_id}")
async def patch_antispam_config(guild_id: int, body: Dict[str, Any], user=Depends(require_admin)) -> Dict[str, Any]:
    """Atualiza a configuração do antispam.

    Campos aceitos:
    - `config` (dict): campos do AntispamConfig mesclados com os atuais (top-level).
      Para campos aninhados (scores, ladder, listas), envie o objeto completo.
    - `enabled` (bool): ativa/desativa o antispam.
    """
    if not body:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body vazio")

    unknown = set(body) - {"config", "enabled"}
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos não permitidos: {sorted(unknown)}",
        )

    async with api_db.acquire() as conn:
        # Garante que a row existe com defaults
        await conn.execute(
            "INSERT INTO antispam_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            guild_id,
        )

        if "config" in body:
            # Mescla top-level: campos enviados substituem; demais permanecem
            await conn.execute(
                """
                UPDATE antispam_config
                SET config = config || $2::jsonb, updated_at = NOW()
                WHERE guild_id = $1
                """,
                guild_id,
                body["config"],
            )

        if "enabled" in body:
            await conn.execute(
                """
                UPDATE antispam_config
                SET enabled = $2, updated_at = NOW()
                WHERE guild_id = $1
                """,
                guild_id,
                bool(body["enabled"]),
            )

        row = await conn.fetchrow(
            "SELECT * FROM antispam_config WHERE guild_id = $1", guild_id
        )

    try:
        async with api_db.acquire() as conn2:
            await conn2.execute("SELECT pg_notify('fenrir_cache', $1)", f"antispam:{guild_id}")
            await write_audit(conn2, guild_id, user, "antispam", body)
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY/audit antispam: %s", exc)

    return dict(row)


# ─── audit ───────────────────────────────────────────────────────────────────

@router.get("/audit/{guild_id}", dependencies=[Depends(require_admin)])
async def get_audit_log(
    guild_id: int,
    user_id:  Optional[int] = Query(default=None),
    page:     int           = Query(default=0, ge=0),
    per_page: int           = Query(default=50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Lista eventos do antispam_audit. Filtro opcional por `user_id`."""
    offset = page * per_page

    async with api_db.acquire() as conn:
        if user_id is not None:
            rows = await conn.fetch(
                """
                SELECT * FROM antispam_audit
                WHERE guild_id = $1 AND user_id = $2
                ORDER BY created_at DESC LIMIT $3 OFFSET $4
                """,
                guild_id, user_id, per_page, offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM antispam_audit
                WHERE guild_id = $1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
                """,
                guild_id, per_page, offset,
            )

    return [dict(r) for r in rows]
