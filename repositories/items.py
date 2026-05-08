"""Repositório para a tabela `items` (loja)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


async def get_all(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM items ORDER BY preco DESC")
    return [dict(r) for r in rows]


async def get_by_id(pool, item_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
    return dict(row) if row else None


async def create(
    pool,
    *,
    nome: str,
    preco: int,
    descricao: Optional[str],
    cooldown_h: float,
    criado_por: int,
) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO items (nome, preco, descricao, cooldown_h, criado_por) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING *",
            nome,
            preco,
            descricao,
            cooldown_h,
            criado_por,
        )
    return dict(row)


async def delete_one(pool, item_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM items WHERE id = $1 RETURNING *", item_id
        )
    return dict(row) if row else None


async def delete_all(pool) -> int:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM items")
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0
