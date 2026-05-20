"""FastAPI — painel administrativo do Fenrir.

Phase 5: Discord OAuth2, webhook Mercado Pago, endpoints antispam/antinuke.
"""

from __future__ import annotations

import logging
import os
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from . import db as api_db
from .routers import antinuke as antinuke_router
from .routers import antispam as antispam_router
from .routers import auth as auth_router
from .routers import config as config_router
from .routers import features as features_router
from .routers import global_config as global_config_router
from .routers import server as server_router
from .routers import items as items_router
from .routers import premium as premium_router
from .routers import users as users_router
from .routers import webhooks as webhooks_router

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
    version="0.5.0",
    description="API administrativa do Fenrir — Phase 5 (auth + webhook MP + painel).",
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


app.include_router(auth_router.router)
app.include_router(webhooks_router.router)
app.include_router(server_router.router)
app.include_router(config_router.router)
app.include_router(features_router.router)
app.include_router(global_config_router.router)
app.include_router(items_router.router)
app.include_router(premium_router.router)
app.include_router(users_router.router)
app.include_router(antispam_router.router)
app.include_router(antinuke_router.router)
