"""FastAPI — painel administrativo do Fenrir.

Estado atual (Fase 0): scaffold com endpoints de saúde e leitura de
`server_config`. Autenticação OAuth2, painel completo e webhook MP serão
adicionados na Fase 5.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from . import db as api_db
from .routers import config as config_router
from .routers import items as items_router
from .routers import users as users_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("fenrir.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await api_db.init_pool()
    yield
    await api_db.close_pool()


app = FastAPI(
    title="Fenrir Admin API",
    version="0.1.0",
    description="API administrativa do Fenrir — Fase 0 (scaffold).",
    lifespan=lifespan,
)

# CORS aberto em dev; restringir em produção via env quando o painel for entregue.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    """Liveness + readiness check. Inclui ping ao banco."""
    db_ok = False
    try:
        async with api_db.acquire() as conn:
            db_ok = (await conn.fetchval("SELECT 1")) == 1
    except Exception as exc:
        log.warning("Health check DB falhou: %s", exc)

    return {"status": "ok" if db_ok else "degraded", "db": db_ok}


app.include_router(config_router.router)
app.include_router(items_router.router)
app.include_router(users_router.router)
