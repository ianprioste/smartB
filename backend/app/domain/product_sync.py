"""Bling product sync helpers for webhook-driven updates."""
from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.logging import get_logger
from app.repositories.product_snapshot_repo import ProductSnapshotRepository

logger = get_logger(__name__)


def _is_delete_event(event_type: str) -> bool:
    et = (event_type or "").strip().lower()
    return any(token in et for token in ("delete", "deleted", "exclu", "remov"))


def _invalidate_all_catalog_cache_keys() -> None:
    try:
        from app.api.bling_products import _catalog_cache
        for key in list(_catalog_cache.keys()):
            if key.startswith("__all__::"):
                _catalog_cache.pop(key, None)
    except Exception:
        pass


async def sync_single_product(
    db: Session,
    tenant_id: UUID,
    client,
    bling_product_id: int,
    event_type: str = "product.updated",
) -> Dict[str, Any]:
    """Fetch and upsert a single product by Bling ID."""
    if _is_delete_event(event_type):
        deleted = ProductSnapshotRepository.delete_product_and_children(
            db,
            tenant_id,
            int(bling_product_id),
        )
        _invalidate_all_catalog_cache_keys()
        db.commit()
        logger.info(
            "webhook_single_product_deleted tenant_id=%s product_id=%s deleted_rows=%s event_type=%s",
            str(tenant_id),
            int(bling_product_id),
            deleted,
            event_type,
        )
        return {
            "ok": True,
            "bling_product_id": int(bling_product_id),
            "deleted_rows": deleted,
            "event_type": event_type,
        }

    try:
        detail = await client.get_product(int(bling_product_id))
    except Exception as exc:
        return {"ok": False, "bling_product_id": int(bling_product_id), "error": str(exc)}

    if not detail:
        return {"ok": False, "bling_product_id": int(bling_product_id), "error": "empty_detail"}

    ProductSnapshotRepository.upsert_product_detail(db, tenant_id, detail)

    # Invalidate the all-products cache keys so the next list/all request re-reads the
    # updated snapshot. Query-specific cache entries (e.g. SKU lookups) are kept intact
    # since they remain valid for unrelated products.
    _invalidate_all_catalog_cache_keys()

    db.commit()
    logger.info(
        "webhook_single_product_synced tenant_id=%s product_id=%s event_type=%s",
        str(tenant_id),
        int(bling_product_id),
        event_type,
    )
    return {"ok": True, "bling_product_id": int(bling_product_id), "event_type": event_type}
