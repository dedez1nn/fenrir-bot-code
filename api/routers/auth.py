"""Discord OAuth2 — autenticação do painel administrativo (Phase 5).

Fluxo: /auth/authorize → Discord → /auth/callback → JWT em cookie HttpOnly.
`require_admin` é exportado como dependência FastAPI para proteger routers.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ─── config ───────────────────────────────────────────────────────────────────

_CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
_REDIRECT_URI  = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
_JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production")
_JWT_ALGO      = "HS256"
_JWT_TTL_H     = 12

_DISCORD_OAUTH_BASE = "https://discord.com/api/oauth2"
_DISCORD_API_BASE   = "https://discord.com/api/v10"

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# IDs de cargo com acesso ao painel (CSV). Se vazio, qualquer membro da guild tem acesso.
_raw_role_ids = os.getenv("ADMIN_ROLE_IDS", "")
_ADMIN_ROLE_IDS: set[int] = {int(x) for x in _raw_role_ids.split(",") if x.strip()}

# Em desenvolvimento (JWT_SECRET padrão) a validação de token é dispensada.
_DEV_MODE = _JWT_SECRET == "change-me-in-production"


# ─── helpers JWT ─────────────────────────────────────────────────────────────

def _create_jwt(user_id: int, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=_JWT_TTL_H)
    return jwt.encode(
        {"sub": str(user_id), "name": username, "exp": exp},
        _JWT_SECRET,
        algorithm=_JWT_ALGO,
    )


def _decode_jwt(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])


# ─── dependência pública ──────────────────────────────────────────────────────

async def require_admin(session: Optional[str] = Cookie(default=None)) -> dict:
    """Dependência FastAPI — valida cookie de sessão JWT.

    Em desenvolvimento (JWT_SECRET não configurado), passa sem validar e
    retorna payload mock. Em produção exige cookie válido + JWT não expirado.
    """
    if _DEV_MODE:
        log.debug("require_admin: dev mode — autenticação dispensada.")
        return {"sub": "0", "name": "dev"}

    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    try:
        payload = _decode_jwt(session)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return payload


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("/authorize")
async def authorize():
    """Redireciona o browser para o OAuth2 Discord."""
    if not _CLIENT_ID:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DISCORD_CLIENT_ID não configurado",
        )
    params = urlencode({
        "client_id":     _CLIENT_ID,
        "redirect_uri":  _REDIRECT_URI,
        "response_type": "code",
        "scope":         "identify guilds.members.read",
    })
    return Response(
        status_code=302,
        headers={"Location": f"{_DISCORD_OAUTH_BASE}/authorize?{params}"},
    )


@router.get("/callback")
async def callback(code: str):
    """Troca o código OAuth2 por token, valida membro + cargo e emite JWT."""
    if not _CLIENT_ID or not _CLIENT_SECRET:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth2 não configurado (CLIENT_ID / CLIENT_SECRET ausentes)",
        )

    async with httpx.AsyncClient() as client:
        # 1. Trocar code → access_token
        token_resp = await client.post(
            f"{_DISCORD_OAUTH_BASE}/token",
            data={
                "client_id":     _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  _REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falha ao obter token Discord")
        access_token = token_resp.json()["access_token"]

        # 2. Identidade do usuário
        user_resp = await client.get(
            f"{_DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falha ao obter usuário Discord")
        user_data = user_resp.json()
        user_id  = int(user_data["id"])
        username = user_data["username"]

        # 3. Verificar membro na guild + cargo de admin
        if GUILD_ID:
            member_resp = await client.get(
                f"{_DISCORD_API_BASE}/users/@me/guilds/{GUILD_ID}/member",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if member_resp.status_code != 200:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Você não faz parte do servidor Fenrir",
                )
            if _ADMIN_ROLE_IDS:
                member_roles = {int(r) for r in member_resp.json().get("roles", [])}
                if not (member_roles & _ADMIN_ROLE_IDS):
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        detail="Você não tem cargo de administrador",
                    )

    jwt_token = _create_jwt(user_id, username)
    resp = Response(
        status_code=200,
        content='{"status":"ok"}',
        media_type="application/json",
    )
    resp.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=_JWT_TTL_H * 3600,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
    )
    return resp


@router.post("/logout")
async def logout():
    """Remove o cookie de sessão."""
    resp = Response(
        status_code=200,
        content='{"status":"ok"}',
        media_type="application/json",
    )
    resp.delete_cookie("session")
    return resp


@router.get("/me")
async def me(payload: dict = Depends(require_admin)):
    """Retorna os dados do usuário autenticado."""
    return {"user_id": payload["sub"], "username": payload["name"]}
