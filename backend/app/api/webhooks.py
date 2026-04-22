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


def _extract_product_id(payload: Dict[str, Any]) -> Optional[int]:
    """Try to extract bling_product_id from product/stock webhook payloads."""
    if isinstance(payload.get("data"), dict):
        candidate = payload["data"].get("id") or payload["data"].get("idProduto")
        if candidate:
            return int(candidate)

    if "id" in payload:
        try:
            return int(payload["id"])
        except (TypeError, ValueError):
            pass

    if "idProduto" in payload:
        try:
            return int(payload["idProduto"])
        except (TypeError, ValueError):
            pass

    if isinstance(payload.get("produto"), dict):
        candidate = payload["produto"].get("id") or payload["produto"].get("idProduto")
        if candidate:
            return int(candidate)

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


def _dispatch_product_task(event_id: str, bling_product_id: int, event_kind: str, event_type: str) -> None:
    """Dispatch product/stock webhook processing with Windows fallback."""
    if platform.system() != "Windows":
        try:
            from app.workers.tasks import process_webhook_product_task
            process_webhook_product_task.delay(event_id, bling_product_id, event_kind, event_type)
            return
        except Exception as exc:
            logger.warning("celery_dispatch_product_failed fallback_to_thread error=%s", str(exc))

    def _run():
        from app.repositories.webhook_repo import WebhookEventRepository as WHR
        from app.repositories.bling_token_repo import BlingTokenRepository
        from app.infra.bling_client import BlingClient
        from app.domain.product_sync import sync_single_product

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
                sync_single_product(
                    db,
                    DEFAULT_TENANT_ID,
                    client,
                    bling_product_id,
                    event_type=event_type,
                )
            )
            if result.get("ok"):
                WHR.mark_processed(db, _uuid.UUID(event_id))
            else:
                WHR.mark_failed(db, _uuid.UUID(event_id), result.get("error", "unknown"))
        except Exception as exc:
            WHR.mark_failed(db, _uuid.UUID(event_id), str(exc))
            logger.error("webhook_%s_thread_failed event_id=%s error=%s", event_kind, event_id, str(exc))
        finally:
            if client:
                try:
                    asyncio.run(client.client.aclose())
                except Exception:
                    pass
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


async def _receive_product_like_webhook(
    request: Request,
    db: Session,
    authorization: Optional[str],
    default_event: str,
    event_kind: str,
):
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
        raise HTTPException(status_code=400, detail="Payload inválido - esperado JSON.")

    event_type = payload.get("event") or payload.get("topic") or default_event
    bling_product_id = _extract_product_id(payload)
    if not bling_product_id:
        logger.warning("webhook_%s_product_id_missing payload_keys=%s", event_kind, list(payload.keys()))
        raise HTTPException(status_code=400, detail="Campo 'id' do produto não encontrado no payload.")

    idempotency_key = _build_idempotency_key(event_type, bling_product_id, payload)
    event = WebhookEventRepository.create_if_new(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        idempotency_key=idempotency_key,
        event_type=event_type,
        bling_order_id=bling_product_id,
        raw_payload=payload,
    )

    if event is None:
        logger.info(
            "webhook_%s_duplicate_skipped idempotency_key=%s bling_product_id=%s",
            event_kind,
            idempotency_key,
            bling_product_id,
        )
        return {"ok": True, "status": "duplicate_skipped", "bling_product_id": bling_product_id}

    _dispatch_product_task(str(event.id), bling_product_id, event_kind, event_type)
    logger.info(
        "webhook_%s_accepted event_id=%s event_type=%s bling_product_id=%s",
        event_kind,
        str(event.id),
        event_type,
        bling_product_id,
    )
    return {
        "ok": True,
        "status": "accepted",
        "event_id": str(event.id),
        "bling_product_id": bling_product_id,
    }


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


@router.post("/bling/products", status_code=202)
@router.post("/bling/products/updated", status_code=202)
async def receive_bling_product_webhook(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Receive product webhook events and refresh product snapshot."""
    return await _receive_product_like_webhook(
        request=request,
        db=db,
        authorization=authorization,
        default_event="product.updated",
        event_kind="product",
    )


@router.post("/bling/stock", status_code=202)
@router.post("/bling/stock/updated", status_code=202)
async def receive_bling_stock_webhook(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Receive stock webhook events and refresh product stock snapshot."""
    return await _receive_product_like_webhook(
        request=request,
        db=db,
        authorization=authorization,
        default_event="stock.updated",
        event_kind="stock",
    )


@router.post("/bling/suppliers", status_code=202)
@router.post("/bling/suppliers/updated", status_code=202)
async def receive_bling_suppliers_webhook(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Receive supplier webhook events and refresh supplier snapshot."""
    return await _receive_product_like_webhook(
        request=request,
        db=db,
        authorization=authorization,
        default_event="supplier.updated",
        event_kind="supplier",
    )


@router.get("/health")
async def webhooks_health(db: Session = Depends(get_db)):
    """Operational health summary for webhook pipeline."""
    summary = WebhookEventRepository.health_summary(db, DEFAULT_TENANT_ID)
    return {
        "ok": True,
        "webhooks_enabled": settings.WEBHOOKS_ENABLED,
        **summary,
    }


@router.post("/bling/register-order-webhook", status_code=200)
async def register_bling_order_webhook(db: Session = Depends(get_db)):
    """Register this app's webhook URL in Bling for order status updates.
    
    This creates a webhook subscription in Bling that will POST to:
    POST /webhooks/bling/orders whenever an order is updated.
    """
    from app.repositories.bling_token_repo import BlingTokenRepository
    from app.infra.bling_client import BlingClient

    if not settings.PUBLIC_API_URL:
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_API_URL not configured. Cannot register webhook without public URL."
        )

    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        raise HTTPException(status_code=401, detail="Bling não autenticado. Configure o token de acesso.")

    def _save(at, rt, ea):
        from app.repositories.bling_token_repo import BlingTokenRepository as TR
        TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

    client = BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )

    webhook_url = f"{settings.PUBLIC_API_URL}/webhooks/bling/orders"
    webhook_secret = settings.BLING_WEBHOOK_SECRET or "smartbling-webhook-secret"

    try:
        # Register webhook in Bling
        payload = {
            "nome": "SmartBling Order Sync",
            "url": webhook_url,
            "recurso": "pedidos",
            "eventos": ["pedido.atualizado"],
            "modulo": 98310,  # Pedidos de Vendas module
        }
        
        response = await client.post("/webhooks", payload)
        
        logger.info(
            "bling_webhook_registered webhook_url=%s response=%s",
            webhook_url,
            response,
        )
        
        return {
            "ok": True,
            "message": "Webhook registrado no Bling com sucesso",
            "webhook_url": webhook_url,
            "response": response,
        }
    except Exception as exc:
        logger.error(
            "bling_webhook_registration_failed webhook_url=%s error=%s",
            webhook_url,
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao registrar webhook no Bling: {str(exc)}"
        )


@router.get("/bling/list-webhooks", status_code=200)
async def list_bling_webhooks(db: Session = Depends(get_db)):
    """List all webhooks registered in Bling."""
    from app.repositories.bling_token_repo import BlingTokenRepository
    from app.infra.bling_client import BlingClient

    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        raise HTTPException(status_code=401, detail="Bling não autenticado. Configure o token de acesso.")

    def _save(at, rt, ea):
        from app.repositories.bling_token_repo import BlingTokenRepository as TR
        TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

    client = BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )

    try:
        response = await client.get("/webhooks")
        webhooks = response.get("data", []) if isinstance(response, dict) else []
        
        logger.info(
            "bling_webhooks_listed count=%d",
            len(webhooks),
        )
        
        return {
            "ok": True,
            "webhooks": webhooks,
            "count": len(webhooks),
        }
    except Exception as exc:
        logger.error(
            "bling_webhooks_list_failed error=%s",
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao listar webhooks do Bling: {str(exc)}"
        )


@router.post("/bling/register-product-webhook", status_code=200)
async def register_bling_product_webhook(db: Session = Depends(get_db)):
    """Register webhook for product updates."""
    from app.repositories.bling_token_repo import BlingTokenRepository
    from app.infra.bling_client import BlingClient

    if not settings.PUBLIC_API_URL:
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_API_URL not configured."
        )

    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        raise HTTPException(status_code=401, detail="Bling não autenticado.")

    def _save(at, rt, ea):
        from app.repositories.bling_token_repo import BlingTokenRepository as TR
        TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

    client = BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )

    webhook_url = f"{settings.PUBLIC_API_URL}/webhooks/bling/products"

    try:
        payload = {
            "nome": "SmartBling Product Sync",
            "url": webhook_url,
            "recurso": "produtos",
            "eventos": ["produto.atualizado"],
        }
        
        response = await client.post("/webhooks", payload)
        logger.info("bling_product_webhook_registered url=%s", webhook_url)
        
        return {
            "ok": True,
            "message": "Webhook de produtos registrado com sucesso",
            "webhook_url": webhook_url,
        }
    except Exception as exc:
        logger.error("bling_product_webhook_failed error=%s", str(exc))
        raise HTTPException(status_code=500, detail=f"Falha: {str(exc)}")


@router.post("/bling/register-stock-webhook", status_code=200)
async def register_bling_stock_webhook(db: Session = Depends(get_db)):
    """Register webhook for stock updates."""
    from app.repositories.bling_token_repo import BlingTokenRepository
    from app.infra.bling_client import BlingClient

    if not settings.PUBLIC_API_URL:
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_API_URL not configured."
        )

    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        raise HTTPException(status_code=401, detail="Bling não autenticado.")

    def _save(at, rt, ea):
        from app.repositories.bling_token_repo import BlingTokenRepository as TR
        TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

    client = BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )

    webhook_url = f"{settings.PUBLIC_API_URL}/webhooks/bling/stock"

    try:
        payload = {
            "nome": "SmartBling Stock Sync",
            "url": webhook_url,
            "recurso": "estoque",
            "eventos": ["estoque.atualizado"],
        }
        
        response = await client.post("/webhooks", payload)
        logger.info("bling_stock_webhook_registered url=%s", webhook_url)
        
        return {
            "ok": True,
            "message": "Webhook de estoque registrado com sucesso",
            "webhook_url": webhook_url,
        }
    except Exception as exc:
        logger.error("bling_stock_webhook_failed error=%s", str(exc))
        raise HTTPException(status_code=500, detail=f"Falha: {str(exc)}")


@router.post("/bling/register-supplier-webhook", status_code=200)
async def register_bling_supplier_webhook(db: Session = Depends(get_db)):
    """Register webhook for supplier updates."""
    from app.repositories.bling_token_repo import BlingTokenRepository
    from app.infra.bling_client import BlingClient

    if not settings.PUBLIC_API_URL:
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_API_URL not configured."
        )

    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        raise HTTPException(status_code=401, detail="Bling não autenticado.")

    def _save(at, rt, ea):
        from app.repositories.bling_token_repo import BlingTokenRepository as TR
        TR.create_or_update(db, DEFAULT_TENANT_ID, at, rt, ea)

    client = BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )

    webhook_url = f"{settings.PUBLIC_API_URL}/webhooks/bling/suppliers"

    try:
        payload = {
            "nome": "SmartBling Supplier Sync",
            "url": webhook_url,
            "recurso": "fornecedores",
            "eventos": ["fornecedor.atualizado"],
        }
        
        response = await client.post("/webhooks", payload)
        logger.info("bling_supplier_webhook_registered url=%s", webhook_url)
        
        return {
            "ok": True,
            "message": "Webhook de fornecedores registrado com sucesso",
            "webhook_url": webhook_url,
        }
    except Exception as exc:
        logger.error("bling_supplier_webhook_failed error=%s", str(exc))
        raise HTTPException(status_code=500, detail=f"Falha: {str(exc)}")


@router.post("/bling/register-all-webhooks", status_code=200)
async def register_all_bling_webhooks(db: Session = Depends(get_db)):
    """Register all webhooks at once: orders, products, stock, suppliers."""
    results = {}
    
    try:
        # Register order webhook
        try:
            order_result = await register_bling_order_webhook(db)
            results["orders"] = {"ok": True, "url": order_result.get("webhook_url")}
        except Exception as e:
            results["orders"] = {"ok": False, "error": str(e)}
    except:
        results["orders"] = {"ok": False, "error": "Failed"}

    try:
        # Register product webhook
        try:
            product_result = await register_bling_product_webhook(db)
            results["products"] = {"ok": True, "url": product_result.get("webhook_url")}
        except Exception as e:
            results["products"] = {"ok": False, "error": str(e)}
    except:
        results["products"] = {"ok": False, "error": "Failed"}

    try:
        # Register stock webhook
        try:
            stock_result = await register_bling_stock_webhook(db)
            results["stock"] = {"ok": True, "url": stock_result.get("webhook_url")}
        except Exception as e:
            results["stock"] = {"ok": False, "error": str(e)}
    except:
        results["stock"] = {"ok": False, "error": "Failed"}

    try:
        # Register supplier webhook
        try:
            supplier_result = await register_bling_supplier_webhook(db)
            results["suppliers"] = {"ok": True, "url": supplier_result.get("webhook_url")}
        except Exception as e:
            results["suppliers"] = {"ok": False, "error": str(e)}
    except:
        results["suppliers"] = {"ok": False, "error": "Failed"}

    all_ok = all(r.get("ok", False) for r in results.values())
    
    return {
        "ok": all_ok,
        "message": "Webhooks registrados" if all_ok else "Alguns webhooks falharam",
        "results": results,
    }
