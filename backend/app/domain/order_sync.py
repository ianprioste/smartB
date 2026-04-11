"""Bling orders import/sync service to persistent local database."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.logging import get_logger
from app.repositories.order_snapshot_repo import OrderSnapshotRepository
from app.utils.datetime_utils import now_local

logger = get_logger(__name__)


async def sync_orders(
    db: Session,
    tenant_id: UUID,
    client,
    mode: str,
    max_concurrency: int = 3,
) -> Dict[str, Any]:
    """Run full or incremental sync from Bling into local DB snapshots."""
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")

    state = OrderSnapshotRepository.get_or_create_sync_state(db, tenant_id)

    if mode == "full":
        list_orders = await _fetch_all_orders(client)
    else:
        # Bling date filters are based on order date and can miss status-only
        # changes on older orders. For correctness, incremental fetches all
        # orders and only differs from full by operational intent.
        list_orders = await _fetch_all_orders(client)

    if not list_orders:
        msg = f"sync {mode}: no orders returned"
        OrderSnapshotRepository.mark_sync_success(db, tenant_id, mode, msg)
        db.commit()
        return {"mode": mode, "total_listed": 0, "upserted": 0, "failed": 0, "message": msg}

    total = len(list_orders)
    OrderSnapshotRepository.mark_sync_running(
        db,
        tenant_id,
        mode,
        f"processed=0|total={total}|upserted=0|failed=0",
    )
    db.commit()

    processed = 0
    upserted = 0
    failed = 0

    # Process in small batches to avoid event-loop congestion and allow
    # progress commits that are visible from other threads/connections.
    batch_size = max_concurrency

    for batch_start in range(0, total, batch_size):
        batch = list_orders[batch_start : batch_start + batch_size]

        async def _fetch_detail(order: Dict[str, Any]):
            order_id = order.get("id")
            if order_id is None:
                return order, None, ValueError("missing order id")
            try:
                detail = await client.get(f"/pedidos/vendas/{order_id}")
                return order, detail, None
            except Exception as exc:
                return order, None, exc

        results = await asyncio.gather(*[_fetch_detail(o) for o in batch])

        for order, detail, err in results:
            if err is not None or detail is None:
                failed += 1
            else:
                OrderSnapshotRepository.upsert_order(db, tenant_id, order, detail)
                upserted += 1
            processed += 1

        OrderSnapshotRepository.mark_sync_running(
            db,
            tenant_id,
            mode,
            f"processed={processed}|total={total}|upserted={upserted}|failed={failed}",
        )
        db.commit()

    msg = f"sync {mode}: listed={total} upserted={upserted} failed={failed}"
    if failed > 0:
        OrderSnapshotRepository.mark_sync_failure(db, tenant_id, msg)
    else:
        OrderSnapshotRepository.mark_sync_success(db, tenant_id, mode, msg)

    db.commit()
    logger.info("orders_sync_done tenant_id=%s mode=%s listed=%s upserted=%s failed=%s", str(tenant_id), mode, total, upserted, failed)

    return {
        "mode": mode,
        "total_listed": total,
        "upserted": upserted,
        "failed": failed,
        "message": msg,
    }


async def _fetch_all_orders(client) -> List[Dict[str, Any]]:
    page = 1
    limit = 100
    all_orders: List[Dict[str, Any]] = []

    while True:
        params: List[tuple] = [("pagina", page), ("limite", limit)]

        resp = await client.get("/pedidos/vendas", params=params)
        page_data = resp.get("data", []) if isinstance(resp, dict) else []
        if not page_data:
            break

        all_orders.extend(page_data)
        if len(page_data) < limit:
            break

        page += 1
        if page > 500:
            break

    return all_orders


async def _fetch_orders_by_date_range(
    client,
    start_dt: datetime,
    end_dt: datetime,
) -> List[Dict[str, Any]]:
    page = 1
    limit = 100
    all_orders: List[Dict[str, Any]] = []

    while True:
        params: List[tuple] = [
            ("pagina", page),
            ("limite", limit),
            ("dataInicial", start_dt.strftime("%Y-%m-%d")),
            ("dataFinal", end_dt.strftime("%Y-%m-%d")),
        ]

        resp = await client.get("/pedidos/vendas", params=params)
        page_data = resp.get("data", []) if isinstance(resp, dict) else []
        if not page_data:
            break

        all_orders.extend(page_data)
        if len(page_data) < limit:
            break

        page += 1
        if page > 500:
            break

    return all_orders