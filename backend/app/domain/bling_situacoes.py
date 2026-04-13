"""Discover and cache Bling situation (status) IDs for the Pedidos de Vendas module.

If the Bling account doesn't have the 'Situações' scope enabled, discovery
falls back to well-known standard IDs (9 = Atendido).  Custom statuses like
"Pronto para Envio / Retirada" require the scope or manual configuration.
"""
from __future__ import annotations

from typing import Dict, Optional
import os

from app.infra.logging import get_logger

logger = get_logger(__name__)

# Bling system module ID for "Pedidos de Vendas" — standard across accounts.
VENDAS_MODULE_ID = 98310

# In-memory cache (lives for the process lifetime, which is fine for uvicorn workers).
_cached_ids: Optional[Dict[str, int]] = None

# Well-known standard Bling status IDs (work without the Situações scope).
_FALLBACK_IDS: Dict[str, int] = {
    "atendido": 9,
}


def _env_status_ids() -> Dict[str, int]:
    """Load optional status IDs from environment variables.

    Useful when the token does not have Situações scope.
    """
    mapping = {
        "pronto_envio": os.getenv("BLING_STATUS_PRONTO_ENVIO_ID", "").strip(),
        "pronto_retirada": os.getenv("BLING_STATUS_PRONTO_RETIRADA_ID", "").strip(),
        "atendido": os.getenv("BLING_STATUS_ATENDIDO_ID", "").strip(),
    }
    resolved: Dict[str, int] = {}
    for key, raw in mapping.items():
        if not raw:
            continue
        try:
            resolved[key] = int(raw)
        except ValueError:
            logger.warning("invalid_env_status_id key=%s value=%s", key, raw)
    return resolved

# Names we look for (case-insensitive substring matching) when discovery works.
_TARGETS = {
    "pronto_envio": "pronto para envio",
    "pronto_retirada": "pronto para retirada",
    "atendido": "atendido",
}


async def get_bling_status_ids(client) -> Dict[str, int]:
    """Return a dict mapping logical names to Bling situation IDs.

    Keys: 'pronto_envio', 'pronto_retirada', 'atendido'.
    Values may be missing if the status doesn't exist in the account.
    Falls back to well-known IDs when the Situações scope is not available.
    """
    global _cached_ids
    if _cached_ids is not None:
        return _cached_ids

    env_ids = _env_status_ids()

    try:
        resp = await client.get(f"/situacoes/modulos/{VENDAS_MODULE_ID}")
        items = resp.get("data", []) if isinstance(resp, dict) else []
        if not isinstance(items, list):
            items = []
    except Exception as exc:
        logger.warning(
            "bling_situacoes_fetch_failed error=%s — using fallback IDs",
            str(exc),
        )
        _cached_ids = {**_FALLBACK_IDS, **env_ids}
        logger.info("bling_situacoes_fallback ids=%s", _cached_ids)
        return _cached_ids

    result: Dict[str, int] = {}

    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get("nome") or "").strip().lower()
        sit_id = item.get("id")
        if not name or sit_id is None:
            continue
        for key, target in _TARGETS.items():
            if key not in result and target in name:
                result[key] = int(sit_id)

    # Merge env overrides and ensure atendido always has a value.
    result.update(env_ids)

    # Ensure atendido always has a value (use fallback if discovery/env missed it).
    for key, fallback_id in _FALLBACK_IDS.items():
        if key not in result:
            result[key] = fallback_id

    _cached_ids = result
    logger.info("bling_situacoes_resolved ids=%s", result)
    return result


def clear_cache():
    """Reset cached IDs (useful after reconnecting Bling account)."""
    global _cached_ids
    _cached_ids = None
