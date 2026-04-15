"""Bling webhook receiver endpoint.

Accepts POST /webhooks/bling/orders (and /orders/updated) from Bling.
Validates the shared secret (Authorization header), persists the event for
idempotency, and dispatches an async Celery task to refresh the order snapshot.
Falls back to local background thread on Windows when Celery is unavailable.
"""
from __future__ import annotations

import hashlib
import hmac
import platform
import threading
import asyncio
import uuid as _uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.infra.db import SessionLocal
from app.infra.logging import get_logger
from app.settings import settings
from app.repositories.webhook_repo import WebhookEventRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DEFAULT_TENANT_ID = _uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------

def _verify_secret(authorization: Optional[str]) -> bool:
    """Return True if the Authorization header matches BLING_WEBHOOK_SECRET.

    Accepts formats:
      - Bearer <secret>
      - <secret>          (bare token)

    If BLING_WEBHOOK_SECRET is empty (not configured), the check is skipped so
    that development environments work without extra setup.
    """
    secret = settings.BLING_WEBHOOK_SECRET
    if not secret:
        logger.warning("webhook_secret_not_configured skipping_validation")
        return True

    if not authorization:
        return False

    token = authorization.removeprefix("Bearer ").strip()
    return hmac.compare_digest(token.encode(), secret.encode())


# ---------------------------------------------------------------------------
# Payload normalisation
# ---------------------------------------------------------------------------

def _extract_order_id(payload: Dict[str, Any]) -> Optional[int]:
    """Try to extract bling_order_id from the incoming payload.

    Bling may send the order id inside different keys depending on the event
    type.  We try the most common shapes gracefully.
    """
    # Shape 1: {"data": {"id": 123456, ...}}
    if isinstance(payload.get("data"), dict):
        oid = payload["data"].get("id")
        if oid:
            return int(oid)

    # Shape 2: {"id": 123456}
    if "id" in payload:
        try:
            return int(payload["id"])
        except (TypeError, ValueError):
            pass

    # Shape 3: nested pedido
    if isinstance(payload.get("pedido"), dict):
        oid = payload["pedido"].get("id")
        if oid:
            return int(oid)

    return None


def _build_idempotency_key(event_type: str, order_id: Optional[int], payload: Dict[str, Any]) -> str:
    """Build a stable, unique key for deduplication.

    When a stable event_id is present in the payload we use it directly.
    Otherwise we hash canonical fields so replays of the same logical event
    produce the same key.
    """
    # Bling may include a stable notificationToken or retentationExpiresAt
    ext_id = (
        payload.get("notificationToken")
        or payload.get("retentationExpiresAt")
    )
    if ext_id:
        return f"{event_type}:{ext_id}"

    # Fallback: deterministic hash of event_type + order_id
    raw = f"{event_type}:{order_id}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{event_type}:{order_id}:{digest}"


# ---------------------------------------------------------------------------
# Background dispatch helpers
# ---------------------------------------------------------------------------

def _dispatch_task(event_id: str, bling_order_id: int) -> None:
    """Dispatch the order processing task, with Windows fallback."""
    if platform.system() != "Windows":
        try:
            from app.workers.tasks import process_webhook_order_task
            process_webhook_order_task.delay(event_id, bling_order_id)
            return
        except Exception as exc:
            logger.warning("celery_dispatch_failed fallback_to_thread error=%s", str(exc))

    # Windows / Celery unavailable: run in background thread
    def _run():
        from app.repositories.webhook_repo import WebhookEventRepository as WHR
        from app.repositories.bling_token_repo import BlingTokenRepository
        from app.infra.bling_client import BlingClient
        from app.domain.order_sync import sync_single_order

        db = SessionLocal()
        client = None
        try:
            WHR.set_processing(db, _uuid.UUID(event_id))
            token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
            if not token_row:
                raise RuntimeError("no_bling_token")

            def _save(at, rt, ea):
                from app.repositories.bling_token_repo import BlingTokenRepository as TR
                TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

            client = BlingClient(
                access_token=token_row.access_token,
                refresh_token=token_row.refresh_token,
                token_expires_at=token_row.expires_at,
                on_token_refresh=_save,
            )
            result = asyncio.run(
                sync_single_order(db, DEFAULT_TENANT_ID, client, bling_order_id)
            )
            if result.get("ok"):
                WHR.mark_processed(db, _uuid.UUID(event_id))
            else:
                WHR.mark_failed(db, _uuid.UUID(event_id), result.get("error", "unknown"))
        except Exception as exc:
            WHR.mark_failed(db, _uuid.UUID(event_id), str(exc))
            logger.error("webhook_thread_failed event_id=%s error=%s", event_id, str(exc))
        finally:
            if client:
                try:
                    asyncio.run(client.client.aclose())
                except Exception:
                    pass
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/bling/orders", status_code=202)
@router.post("/bling/orders/updated", status_code=202)
async def receive_bling_order_webhook(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Receive Bling order webhook events.

    Responds with 202 immediately; processing happens asynchronously.
    """
    if not settings.WEBHOOKS_ENABLED:
        raise HTTPException(status_code=503, detail="Webhooks desabilitados no momento.")

    if not _verify_secret(authorization):
        logger.warning(
            "webhook_unauthorized remote=%s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido — esperado JSON.")

    event_type = (
        payload.get("event")
        or payload.get("topic")
        or "order.updated"
    )

    bling_order_id = _extract_order_id(payload)
    if not bling_order_id:
        logger.warning("webhook_order_id_missing payload_keys=%s", list(payload.keys()))
        raise HTTPException(status_code=400, detail="Campo 'id' do pedido não encontrado no payload.")

    idempotency_key = _build_idempotency_key(event_type, bling_order_id, payload)

    event = WebhookEventRepository.create_if_new(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        idempotency_key=idempotency_key,
        event_type=event_type,
        bling_order_id=bling_order_id,
        raw_payload=payload,
    )

    if event is None:
        # Duplicate — already received or processed
        logger.info(
            "webhook_duplicate_skipped idempotency_key=%s bling_order_id=%s",
            idempotency_key,
            bling_order_id,
        )
        return {"ok": True, "status": "duplicate_skipped", "bling_order_id": bling_order_id}

    _dispatch_task(str(event.id), bling_order_id)

    logger.info(
        "webhook_accepted event_id=%s event_type=%s bling_order_id=%s",
        str(event.id),
        event_type,
        bling_order_id,
    )
    return {
        "ok": True,
        "status": "accepted",
        "event_id": str(event.id),
        "bling_order_id": bling_order_id,
    }


@router.get("/health")
async def webhooks_health(db: Session = Depends(get_db)):
    """Operational health summary for webhook pipeline."""
    summary = WebhookEventRepository.health_summary(db, DEFAULT_TENANT_ID)
    return {
        "ok": True,
        "webhooks_enabled": settings.WEBHOOKS_ENABLED,
        **summary,
    }
