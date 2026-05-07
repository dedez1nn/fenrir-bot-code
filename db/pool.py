"""Gerenciamento do pool de conexões asyncpg.

Princípio: o bot nunca crasha por causa do banco. Se `DATABASE_URL` não estiver
definida ou o Postgres estiver indisponível, `init_pool` loga e retorna `None`.
Cogs devem checar `bot.db is not None` antes de usar.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

try:
    import asyncpg
except ImportError:  # asyncpg ainda não instalado durante boot do dev
    asyncpg = None  # type: ignore

log = logging.getLogger(__name__)

_pool: Optional["asyncpg.Pool"] = None


async def _init_connection(conn) -> None:
    """Codec automático: JSONB ↔ dict/list (ao invés de string crua)."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool(dsn: Optional[str] = None, *, min_size: int = 1, max_size: int = 10) -> Optional["asyncpg.Pool"]:
    """Cria o pool global. Retorna `None` em caso de falha.

    Args:
        dsn: connection string. Se `None`, lê de `DATABASE_URL`.
        min_size, max_size: parâmetros do pool asyncpg.
    """
    global _pool

    if asyncpg is None:
        log.warning("asyncpg não instalado — pool indisponível.")
        return None

    if _pool is not None:
        return _pool

    dsn = dsn or os.getenv("DATABASE_URL")
    if not dsn:
        log.warning("DATABASE_URL não definida — pool não inicializado.")
        return None

    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
            init=_init_connection,
        )
        log.info("Pool asyncpg inicializado (%s..%s conexões).", min_size, max_size)
        return _pool
    except Exception as exc:
        log.error("Falha ao inicializar pool asyncpg: %s", exc)
        _pool = None
        return None


async def close_pool() -> None:
    """Encerra o pool global, se existir."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("Pool asyncpg encerrado.")


def get_pool() -> Optional["asyncpg.Pool"]:
    """Acesso direto ao pool. Pode ser `None` se ainda não inicializado."""
    return _pool
