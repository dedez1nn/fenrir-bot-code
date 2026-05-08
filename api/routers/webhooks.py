"""Webhook do Mercado Pago — Phase 5.

Valida a assinatura HMAC do MP, verifica o pagamento via API do MP e atualiza
`users.premium` no banco. Notifica o bot via PostgreSQL NOTIFY para invalidação
imediata de cache e concessão dos benefícios de premium.

Referência MP: https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from .. import db as api_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
_MP_ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN", "")
_MP_API_BASE       = "https://api.mercadopago.com"
_VALID_PLANS       = {"aventureiro", "lendario", "mitico"}


# ─── HMAC ────────────────────────────────────────────────────────────────────

def _verify_mp_signature(ts: str, data_id: str, request_id: str, signature: str) -> bool:
    """Valida x-signature do Mercado Pago.

    Manifesto: `id:{data_id};request-id:{request_id};ts:{ts};`
    Header:    `ts=<ts>,v1=<hex-digest>`
    """
    if not _MP_WEBHOOK_SECRET:
        log.warning("MP_WEBHOOK_SECRET não configurado — HMAC não validado.")
        return True
    try:
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        mac = _hmac.new(
            _MP_WEBHOOK_SECRET.encode(),
            manifest.encode(),
            hashlib.sha256,
        )
        expected = mac.hexdigest()
        v1 = next(
            (p.split("=", 1)[1] for p in signature.split(",") if p.startswith("v1=")),
            "",
        )
        return _hmac.compare_digest(expected, v1)
    except Exception:
        return False


# ─── processamento ───────────────────────────────────────────────────────────

async def _process_approved_payment(payment_id: str) -> None:
    """Verifica o pagamento no MP; atualiza premium no DB; notifica o bot."""
    if not _MP_ACCESS_TOKEN:
        log.error("ACCESS_TOKEN (MP) não configurado — não é possível verificar pagamento.")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_MP_API_BASE}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {_MP_ACCESS_TOKEN}"},
        )

    if resp.status_code != 200:
        log.warning("Falha ao buscar pagamento %s do MP: HTTP %s", payment_id, resp.status_code)
        return

    payment = resp.json()
    if payment.get("status") != "approved":
        log.info("Pagamento %s não aprovado (status=%s) — ignorado.", payment_id, payment.get("status"))
        return

    # external_reference: "premium_{plano}_{user_id}"
    ext_ref = payment.get("external_reference", "")
    parts   = ext_ref.split("_")
    if len(parts) != 3 or parts[0] != "premium":
        log.warning("external_reference inválido: %r", ext_ref)
        return

    plano = parts[1]
    try:
        user_id = int(parts[2])
    except ValueError:
        log.warning("user_id inválido em external_reference: %r", ext_ref)
        return

    if plano not in _VALID_PLANS:
        log.warning("Plano desconhecido: %r", plano)
        return

    # Lê duração de server_config (fallback 30 dias)
    duration_days = 30
    try:
        async with api_db.acquire() as conn:
            row = await conn.fetchrow("SELECT premium_duration_days FROM server_config LIMIT 1")
        if row:
            duration_days = int(row["premium_duration_days"])
    except Exception:
        pass

    expira = datetime.now(timezone.utc) + timedelta(days=duration_days)

    async with api_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, premium, premium_expira)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET
                premium        = EXCLUDED.premium,
                premium_expira = EXCLUDED.premium_expira,
                updated_at     = NOW()
            """,
            user_id,
            plano,
            expira,
        )
        # Notifica o bot para: invalidar cache + conceder role/coins/xp
        await conn.execute(
            "SELECT pg_notify('fenrir_cache', $1)",
            f"premium:{user_id}:{plano}",
        )

    log.info(
        "Premium '%s' ativado para user_id=%s via webhook (expira %s).",
        plano,
        user_id,
        expira.date().isoformat(),
    )


# ─── endpoint ─────────────────────────────────────────────────────────────────

@router.post("/mercadopago", status_code=status.HTTP_200_OK)
async def mercadopago_webhook(
    request:      Request,
    background_tasks: BackgroundTasks,
    x_signature:  str = Header(default=""),
    x_request_id: str = Header(default=""),
):
    """Recebe notificações de pagamento do Mercado Pago.

    Responde 200 imediatamente (contrato MP); processa a verificação em background.
    """
    body = await request.json()

    event_type = body.get("type", "")
    data_id    = str(body.get("data", {}).get("id", ""))

    if event_type != "payment" or not data_id:
        return {"status": "ignored"}

    ts = next(
        (p.split("=", 1)[1] for p in x_signature.split(",") if p.startswith("ts=")),
        "",
    )

    if not _verify_mp_signature(ts, data_id, x_request_id, x_signature):
        log.warning("Assinatura HMAC inválida para payment_id=%s.", data_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida")

    background_tasks.add_task(_process_approved_payment, data_id)
    return {"status": "queued", "payment_id": data_id}
