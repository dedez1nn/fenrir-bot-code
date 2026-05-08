"""Endpoints de leitura/escrita de `server_config`.

Fase 0/2: leitura + escrita parcial (PATCH). Auth Discord OAuth2 será plugada
na Fase 5 via `Depends(require_admin)`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .. import db as api_db

router = APIRouter(prefix="/config", tags=["config"])

_ALLOWED_PATCH_FIELDS = {
    "commands_channel_id",
    "status_channel_id",
    "afk_voice_channel_id",
    "colors_channel_id",
    "pix_channel_id",
    "tickets_channel_id",
    "antispam_log_channel_id",
    "antinuke_log_channel_id",
    "coins_log_channel_id",
    "xp_log_channel_id",
    "levelup_channel_id",
    "admin_ping_ids",
    "levelup_role_map",
    "premium_prices",
    "premium_duration_days",
    "premium_multipliers",
    "daily_coins",
    "daily_streak_bonus",
    "coins_por_mensagem",
    "coins_por_voz",
    "xp_por_mensagem",
    "xp_por_voz",
    "voice_xp_interval_s",
    "bonus_coins_por_nivel",
}


@router.get("/{guild_id}")
async def get_config(guild_id: int) -> Dict[str, Any]:
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM server_config WHERE guild_id = $1", guild_id
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="server_config não existe para esta guild")
    return dict(row)


@router.patch("/{guild_id}")
async def patch_config(guild_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza campos específicos de server_config.

    Somente campos listados em `_ALLOWED_PATCH_FIELDS` são aceitos.
    Campos desconhecidos retornam 422.
    """
    unknown = set(body) - _ALLOWED_PATCH_FIELDS
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos desconhecidos: {sorted(unknown)}",
        )
    if not body:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body vazio")

    # Build SET clause dynamically — safe because field names are allowlisted above
    assigns = []
    params: list[Any] = []
    for i, (field, value) in enumerate(body.items(), start=2):  # $1 = guild_id
        # JSONB fields need explicit cast
        if isinstance(value, (dict, list)):
            assigns.append(f"{field} = ${i}::jsonb")
            params.append(json.dumps(value))
        else:
            assigns.append(f"{field} = ${i}")
            params.append(value)
    assigns.append(f"updated_at = ${len(params) + 2}")
    params.append(datetime.now(timezone.utc))

    sql = f"UPDATE server_config SET {', '.join(assigns)} WHERE guild_id = $1 RETURNING *"

    async with api_db.acquire() as conn:
        row = await conn.fetchrow(sql, guild_id, *params)

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="server_config não existe para esta guild")

    # Notifica o bot para recarregar server_config do banco (invalida cache TTL)
    try:
        async with api_db.acquire() as notify_conn:
            await notify_conn.execute(
                "SELECT pg_notify('fenrir_cache', $1)",
                f"config:{guild_id}",
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Falha ao enviar NOTIFY config: %s", exc)

    return dict(row)
