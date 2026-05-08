"""CRUD de itens da loja via API.

Fase 3: endpoints sem autenticação (auth Discord OAuth2 na Fase 5).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .. import db as api_db

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    nome: str = Field(..., max_length=50)
    preco: int = Field(..., ge=0)
    descricao: Optional[str] = Field(None, max_length=200)
    cooldown_h: float = Field(0.0, ge=0)
    criado_por: int


class ItemUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=50)
    preco: Optional[int] = Field(None, ge=0)
    descricao: Optional[str] = Field(None, max_length=200)
    cooldown_h: Optional[float] = Field(None, ge=0)


@router.get("/", response_model=List[Dict[str, Any]])
async def list_items() -> List[Dict[str, Any]]:
    async with api_db.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM items ORDER BY preco DESC")
    return [dict(r) for r in rows]


@router.get("/{item_id}", response_model=Dict[str, Any])
async def get_item(item_id: int) -> Dict[str, Any]:
    async with api_db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    return dict(row)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def create_item(body: ItemCreate) -> Dict[str, Any]:
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO items (nome, preco, descricao, cooldown_h, criado_por) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING *",
            body.nome,
            body.preco,
            body.descricao,
            body.cooldown_h,
            body.criado_por,
        )
    return dict(row)


@router.patch("/{item_id}", response_model=Dict[str, Any])
async def update_item(item_id: int, body: ItemUpdate) -> Dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum campo fornecido para atualização",
        )
    # Campo names are safe (validated by Pydantic model)
    assigns = [f"{field} = ${i + 2}" for i, field in enumerate(updates.keys())]
    params = list(updates.values())
    sql = f"UPDATE items SET {', '.join(assigns)} WHERE id = $1 RETURNING *"

    async with api_db.acquire() as conn:
        row = await conn.fetchrow(sql, item_id, *params)

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    return dict(row)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int) -> None:
    async with api_db.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM items WHERE id = $1 RETURNING id", item_id
        )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
