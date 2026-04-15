"""Bling product sync helpers for webhook-driven updates."""
from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.logging import get_logger
from app.repositories.product_snapshot_repo import ProductSnapshotRepository

logger = get_logger(__name__)


async def sync_single_product(
    db: Session,
    tenant_id: UUID,
    client,
    bling_product_id: int,
) -> Dict[str, Any]:
    """Fetch and upsert a single product by Bling ID."""
    try:
        detail = await client.get_product(int(bling_product_id))
    except Exception as exc:
        return {"ok": False, "bling_product_id": int(bling_product_id), "error": str(exc)}

    if not detail:
        return {"ok": False, "bling_product_id": int(bling_product_id), "error": "empty_detail"}

    ProductSnapshotRepository.upsert_product_detail(db, tenant_id, detail)

    # Keep product search UX fresh after webhook updates.
    try:
        from app.api.bling_products import invalidate_catalog_cache
        invalidate_catalog_cache()
    except Exception:
        pass

    db.commit()
    logger.info("webhook_single_product_synced tenant_id=%s product_id=%s", str(tenant_id), int(bling_product_id))
    return {"ok": True, "bling_product_id": int(bling_product_id)}
