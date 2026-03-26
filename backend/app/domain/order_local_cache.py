"""Local Redis cache helpers for full Bling order details."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Tuple

from app.infra.redis import redis_client
from app.infra.logging import get_logger

logger = get_logger(__name__)

ORDER_DETAIL_TTL_SECONDS = 60 * 60 * 24
WARM_FLAG_TTL_SECONDS = 60 * 15


def _detail_key(order_id: Any) -> str:
    return f"orders:detail:{order_id}"


def _warm_flag_key(scope: str) -> str:
    return f"orders:detail:warmed:{scope}"


def get_cached_order_detail(order_id: Any) -> Dict[str, Any] | None:
    if order_id is None:
        return None
    try:
        payload = redis_client.get(_detail_key(order_id))
        if not payload:
            return None
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def set_cached_order_detail(order_id: Any, detail: Dict[str, Any]) -> None:
    if order_id is None or not isinstance(detail, dict):
        return
    try:
        redis_client.setex(_detail_key(order_id), ORDER_DETAIL_TTL_SECONDS, json.dumps(detail))
    except Exception:
        # Cache issues should not break request flow.
        return


def is_scope_warmed(scope: str) -> bool:
    try:
        return bool(redis_client.get(_warm_flag_key(scope)))
    except Exception:
        return False


def mark_scope_warmed(scope: str) -> None:
    try:
        redis_client.setex(_warm_flag_key(scope), WARM_FLAG_TTL_SECONDS, "1")
    except Exception:
        return


async def warm_order_details(
    client,
    orders: Iterable[Dict[str, Any]],
    max_concurrency: int = 3,
) -> Tuple[int, int, int]:
    """Warm local cache with /pedidos/vendas/{id} details for all given orders.

    Returns:
        (cache_hits, fetched_from_api, failed)
    """
    cache_hits = 0
    fetched = 0
    failed = 0

    if client is None:
        return cache_hits, fetched, failed

    to_fetch: List[int] = []

    for order in orders:
        if not isinstance(order, dict):
            continue
        order_id = order.get("id")
        if order_id is None:
            continue
        if get_cached_order_detail(order_id) is not None:
            cache_hits += 1
        else:
            try:
                to_fetch.append(int(order_id))
            except Exception:
                continue

    if not to_fetch:
        return cache_hits, fetched, failed

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _fetch_and_store(order_id: int) -> bool:
        try:
            async with semaphore:
                detail = await client.get(f"/pedidos/vendas/{order_id}")
            if isinstance(detail, dict):
                set_cached_order_detail(order_id, detail)
                return True
            return False
        except Exception as exc:
            logger.warning("order_detail_warm_failed order_id=%s error=%s", str(order_id), str(exc))
            return False

    results = await asyncio.gather(*[_fetch_and_store(order_id) for order_id in to_fetch])
    fetched = sum(1 for ok in results if ok)
    failed = len(results) - fetched
    return cache_hits, fetched, failed