"""Fire-and-forget Nuvemshop order status synchronisation.

When the app updates an order status on Bling, call
``sync_order_status_to_nuvemshop`` to mirror the change on Nuvemshop.

This module never raises – all errors are logged and swallowed so the
Bling update path is never blocked.
"""
from __future__ import annotations

from typing import Optional

from app.infra.logging import get_logger
from app.infra.nuvemshop_client import NuvemshopClient, NuvemshopAPIError
from app.settings import settings

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Bling status name → Nuvemshop action
# ---------------------------------------------------------------------------
# Fulfillment statuses: UNPACKED → PACKED → DISPATCHED → DELIVERED
# Order-level: open / closed / cancelled
_STATUS_MAP: dict[str, str] = {
    "pronto para envio": "PACKED",
    "pronto para retirada": "PACKED",
    "atendido": "DISPATCHED",
    "cancelado": "CANCEL",
}


def _resolve_action(bling_status_name: str) -> Optional[str]:
    """Return the Nuvemshop action string or None if no mapping exists."""
    key = bling_status_name.strip().lower()
    for pattern, action in _STATUS_MAP.items():
        if pattern in key:
            return action
    return None


async def sync_order_status_to_nuvemshop(
    numero_loja: Optional[str],
    bling_status_name: str,
) -> None:
    """Best-effort sync of a Bling status change to Nuvemshop.

    Parameters
    ----------
    numero_loja:
        The Nuvemshop order number stored on the Bling snapshot
        (``BlingOrderSnapshotModel.numero_loja``).  If empty/None the
        order didn't originate from Nuvemshop and we skip silently.
    bling_status_name:
        Human-readable Bling status, e.g. "Pronto para envio", "Atendido",
        "Cancelado".
    """
    # Guard: skip if Nuvemshop is not configured.
    if not settings.NUVEMSHOP_ACCESS_TOKEN or not settings.NUVEMSHOP_STORE_ID:
        return
    # Guard: skip orders that didn't come from Nuvemshop.
    if not numero_loja or not str(numero_loja).strip():
        return

    action = _resolve_action(bling_status_name)
    if action is None:
        logger.debug(
            "nuvemshop_sync_skip no_mapping bling_status=%s numero_loja=%s",
            bling_status_name, numero_loja,
        )
        return

    try:
        client = NuvemshopClient()
    except NuvemshopAPIError:
        logger.debug("nuvemshop_sync_skip client_not_configured")
        return

    try:
        # 1. Find the Nuvemshop order by its number.
        ns_order_id = await _find_order_id(client, str(numero_loja).strip())
        if not ns_order_id:
            logger.warning(
                "nuvemshop_order_not_found numero_loja=%s", numero_loja,
            )
            await client.close()
            return

        # 2. Execute the mapped action.
        if action == "CANCEL":
            await client.post(
                f"/orders/{ns_order_id}/cancel",
                json={"reason": "other", "email": False},
            )
            logger.info(
                "nuvemshop_order_cancelled ns_order_id=%s numero_loja=%s",
                ns_order_id, numero_loja,
            )
        else:
            # Fulfillment status update (PACKED / DISPATCHED).
            await _update_fulfillment_status(client, ns_order_id, action, numero_loja)

    except Exception as exc:
        logger.warning(
            "nuvemshop_sync_failed numero_loja=%s action=%s error=%s",
            numero_loja, action, str(exc),
        )
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _find_order_id(client: NuvemshopClient, numero_loja: str) -> Optional[int]:
    """Search Nuvemshop for an order by its number and return its id."""
    try:
        orders = await client.get("/orders", params={"q": numero_loja, "per_page": 5})
    except NuvemshopAPIError as exc:
        logger.warning("nuvemshop_order_search_failed q=%s error=%s", numero_loja, exc)
        return None

    if not isinstance(orders, list):
        return None

    for o in orders:
        if str(o.get("number", "")) == numero_loja:
            return o["id"]
    # Fallback: return first if only one result.
    if len(orders) == 1:
        return orders[0].get("id")
    return None


async def _update_fulfillment_status(
    client: NuvemshopClient,
    ns_order_id: int,
    target_status: str,
    numero_loja: str,
) -> None:
    """Fetch the order's first fulfillment order and PATCH its status."""
    try:
        fulfillments = await client.get(
            f"/orders/{ns_order_id}/fulfillment-orders"
        )
    except NuvemshopAPIError as exc:
        logger.warning(
            "nuvemshop_fulfillment_list_failed ns_order_id=%s error=%s",
            ns_order_id, exc,
        )
        return

    if not isinstance(fulfillments, list) or not fulfillments:
        logger.info(
            "nuvemshop_no_fulfillments ns_order_id=%s numero_loja=%s",
            ns_order_id, numero_loja,
        )
        return

    fo_id = fulfillments[0].get("id")
    if not fo_id:
        return

    await client.patch(
        f"/orders/{ns_order_id}/fulfillment-orders/{fo_id}",
        json={"status": target_status},
    )
    logger.info(
        "nuvemshop_fulfillment_updated ns_order_id=%s fo_id=%s status=%s numero_loja=%s",
        ns_order_id, fo_id, target_status, numero_loja,
    )
