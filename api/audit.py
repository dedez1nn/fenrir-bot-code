"""Helpers de auditoria — escreve entradas em config_audit_log (best effort)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


async def write_audit(
    conn,
    guild_id: int,
    user: Dict[str, Any],
    kind: str,
    patch: Dict[str, Any],
    target: Optional[str] = None,
) -> Optional[int]:
    """Insere uma entrada em config_audit_log e retorna o id gerado.

    Nunca propaga exceções — falha silenciosa para não bloquear o endpoint principal.
    """
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO config_audit_log (guild_id, changed_by, kind, target, patch)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
            """,
            guild_id,
            str(user.get("sub", "unknown")),
            kind,
            target,
            json.dumps(patch),
        )
        return row["id"] if row else None
    except Exception as exc:
        log.warning("Falha ao registrar audit log (guild=%s kind=%s): %s", guild_id, kind, exc)
        return None
