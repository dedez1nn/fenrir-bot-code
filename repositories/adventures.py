"""Repositório para aventuras ativas por usuário (Phase 6).

Cada usuário tem no máximo uma aventura ativa na tabela `adventures`.
O campo `situacao` é JSONB e armazena o dict da situação (nome, descricao, imagem, tipo).
O campo `inicio` é TIMESTAMPTZ; converte para datetime naive UTC ao retornar,
preservando compatibilidade com o código existente em aventurar.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def _naive_utc(dt: datetime) -> datetime:
    """Converte para UTC sem tzinfo (compatibilidade com código legado)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ─── Leitura ──────────────────────────────────────────────────────────────────


async def get_all(pool) -> Dict[str, Any]:
    """Retorna todas as aventuras ativas no formato {str(user_id): aventura_dict}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM adventures")

    result: Dict[str, Any] = {}
    for row in rows:
        uid = str(row["user_id"])
        data: Dict[str, Any] = {
            "inicio":   _naive_utc(row["inicio"]),
            "canal_id": row["canal_id"],
            "situacao": row["situacao"],
        }
        if row["notificado"]:
            data["notificado"] = True
        result[uid] = data

    return result


async def get(pool, user_id: int) -> Optional[Dict[str, Any]]:
    """Retorna a aventura ativa do usuário ou None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM adventures WHERE user_id = $1", user_id
        )

    if not row:
        return None

    data: Dict[str, Any] = {
        "inicio":   _naive_utc(row["inicio"]),
        "canal_id": row["canal_id"],
        "situacao": row["situacao"],
    }
    if row["notificado"]:
        data["notificado"] = True
    return data


# ─── Escrita ──────────────────────────────────────────────────────────────────


async def upsert(
    pool,
    user_id: int,
    inicio: datetime,
    canal_id: Optional[int],
    situacao: dict,
    notificado: bool = False,
) -> None:
    """Cria ou atualiza a aventura ativa do usuário."""
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO adventures (user_id, inicio, canal_id, situacao, notificado, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                inicio     = EXCLUDED.inicio,
                canal_id   = EXCLUDED.canal_id,
                situacao   = EXCLUDED.situacao,
                notificado = EXCLUDED.notificado,
                updated_at = NOW()
            """,
            user_id,
            inicio,
            canal_id,
            json.dumps(situacao),
            notificado,
        )


async def mark_notified(pool, user_id: int) -> None:
    """Marca aventura como notificada sem alterar os demais campos."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE adventures SET notificado = TRUE, updated_at = NOW() WHERE user_id = $1",
            user_id,
        )


async def delete(pool, user_id: int) -> bool:
    """Remove a aventura ativa. Retorna True se havia uma aventura."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM adventures WHERE user_id = $1", user_id
        )
    return result != "DELETE 0"


async def cleanup_expired(pool, max_hours: float = 24.0) -> int:
    """Remove aventuras prontas há mais de `max_hours` horas. Retorna contagem removida."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM adventures WHERE inicio < $1", cutoff
        )
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0
