"""Endpoints de configuração do antinuke — Phase 5.

Todos os endpoints requerem autenticação de administrador.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db as api_db
from ..audit import write_audit
from .auth import require_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/antinuke", tags=["antinuke"])


@router.get("/config/{guild_id}", dependencies=[Depends(require_admin)])
async def get_antinuke_config(guild_id: int) -> Dict[str, Any]:
    """Retorna a configuração atual do antinuke para a guild."""
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM antinuke_config WHERE guild_id = $1", guild_id
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Configuração não encontrada")
    return dict(row)


@router.patch("/config/{guild_id}")
async def patch_antinuke_config(guild_id: int, body: Dict[str, Any], user=Depends(require_admin)) -> Dict[str, Any]:
    """Atualiza a configuração do antinuke.

    Campos aceitos:
    - `config` (dict): campos do AntinukeConfig mesclados com os atuais (top-level).
      Para campos aninhados (severity_thresholds, rates), envie o objeto completo.
    - `enabled` (bool): ativa/desativa o antinuke.
    - `alert_only` (bool): apenas alerta, sem ações automáticas.
    """
    if not body:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body vazio")

    unknown = set(body) - {"config", "enabled", "alert_only"}
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos não permitidos: {sorted(unknown)}",
        )

    async with api_db.acquire() as conn:
        # Garante que a row existe com defaults
        await conn.execute(
            "INSERT INTO antinuke_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            guild_id,
        )

        if "config" in body:
            await conn.execute(
                """
                UPDATE antinuke_config
                SET config = config || $2::jsonb, updated_at = NOW()
                WHERE guild_id = $1
                """,
                guild_id,
                body["config"],
            )

        if "enabled" in body:
            await conn.execute(
                """
                UPDATE antinuke_config
                SET enabled = $2, updated_at = NOW()
                WHERE guild_id = $1
                """,
                guild_id,
                bool(body["enabled"]),
            )

        if "alert_only" in body:
            await conn.execute(
                """
                UPDATE antinuke_config
                SET alert_only = $2, updated_at = NOW()
                WHERE guild_id = $1
                """,
                guild_id,
                bool(body["alert_only"]),
            )

        row = await conn.fetchrow(
            "SELECT * FROM antinuke_config WHERE guild_id = $1", guild_id
        )

    try:
        async with api_db.acquire() as conn2:
            await conn2.execute("SELECT pg_notify('fenrir_cache', $1)", f"antinuke:{guild_id}")
            await write_audit(conn2, guild_id, user, "antinuke", body)
    except Exception as exc:
        log.warning("Falha ao enviar NOTIFY/audit antinuke: %s", exc)

    return dict(row)
