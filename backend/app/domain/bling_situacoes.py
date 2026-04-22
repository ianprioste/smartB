"""Discover and cache Bling situation (status) IDs for the Pedidos de Vendas module.

If the Bling account doesn't have the 'Situações' scope enabled, discovery
falls back to well-known standard IDs (9 = Atendido).  Custom statuses like
"Pronto para Envio / Retirada" require the scope or manual configuration.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import os

from app.infra.logging import get_logger

logger = get_logger(__name__)

# Bling system module ID for "Pedidos de Vendas" — standard across accounts.
VENDAS_MODULE_ID = 98310

# In-memory cache (lives for the process lifetime, which is fine for uvicorn workers).
_cached_ids: Optional[Dict[str, int]] = None
_cached_all_statuses: Optional[List[Dict]] = None

# Well-known standard Bling status IDs (work without the Situações scope).
_FALLBACK_IDS: Dict[str, int] = {
    "em_aberto": 6,
    "atendido": 9,
}

# When Bling does not provide detailed intermediate statuses, map them to
# "Em aberto" so API updates still persist in Bling while the app can keep
# richer local labels (Em andamento, Impedido, Parcialmente entregue).
_OPEN_STATUS_ALIASES = (
    "em_andamento",
    "impedido",
    "parcialmente_entregue",
)


def _env_status_ids() -> Dict[str, int]:
    """Load optional status IDs from environment variables.

    Useful when the token does not have Situações scope.
    """
    mapping = {
        "em_aberto": os.getenv("BLING_STATUS_EM_ABERTO_ID", "").strip(),
        "em_andamento": os.getenv("BLING_STATUS_EM_ANDAMENTO_ID", "").strip(),
        "impedido": os.getenv("BLING_STATUS_IMPEDIDO_ID", "").strip(),
        "parcialmente_entregue": os.getenv("BLING_STATUS_PARCIALMENTE_ENTREGUE_ID", "").strip(),
        "pronto_envio": os.getenv("BLING_STATUS_PRONTO_ENVIO_ID", "").strip(),
        "pronto_retirada": os.getenv("BLING_STATUS_PRONTO_RETIRADA_ID", "").strip(),
        "atendido": os.getenv("BLING_STATUS_ATENDIDO_ID", "").strip(),
        "cancelado": os.getenv("BLING_STATUS_CANCELADO_ID", "").strip(),
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
    "em_aberto": "em aberto",
    "em_andamento": "em andamento",
    "impedido": "impedido",
    "parcialmente_entregue": "parcialmente entregue",
    "pronto_envio": "pronto para envio",
    "pronto_retirada": "pronto para retirada",
    "atendido": "atendido",
    "cancelado": "cancelado",
}


async def get_bling_status_ids(client) -> Dict[str, int]:
    """Return a dict mapping logical names to Bling situation IDs.

    Keys include: 'em_aberto', 'em_andamento', 'impedido',
    'parcialmente_entregue', 'pronto_envio', 'pronto_retirada', 'atendido'.
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

    # Ensure base statuses always have a value (use fallback if discovery/env missed it).
    for key, fallback_id in _FALLBACK_IDS.items():
        if key not in result:
            result[key] = fallback_id

    # If detailed statuses are missing in Bling, alias them to Em aberto ID.
    open_id = result.get("em_aberto")
    if open_id is not None:
        for alias in _OPEN_STATUS_ALIASES:
            if alias not in result:
                result[alias] = int(open_id)

    _cached_ids = result
    logger.info("bling_situacoes_resolved ids=%s", result)
    return result


def clear_cache():
    """Reset cached IDs (useful after reconnecting Bling account)."""
    global _cached_ids, _cached_all_statuses
    _cached_ids = None
    _cached_all_statuses = None


async def get_all_bling_statuses(client) -> List[Dict]:
    """Return ALL Bling order statuses from /situacoes/modulos/{VENDAS_MODULE_ID}.

    Each item: {"id": int, "nome": str, "valor": int|None}.
    Falls back to empty list if the API is unavailable.
    """
    global _cached_all_statuses
    if _cached_all_statuses is not None:
        return _cached_all_statuses

    try:
        resp = await client.get(f"/situacoes/modulos/{VENDAS_MODULE_ID}")
        items = resp.get("data", []) if isinstance(resp, dict) else []
        if not isinstance(items, list):
            items = []
    except Exception as exc:
        logger.warning(
            "bling_all_statuses_fetch_failed error=%s",
            str(exc),
        )
        return []

    result: List[Dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sit_id = item.get("id")
        nome = (item.get("nome") or "").strip()
        if sit_id is None or not nome:
            continue
        valor = item.get("valor")
        result.append({"id": int(sit_id), "nome": nome, "valor": valor})

    _cached_all_statuses = result
    logger.info("bling_all_statuses_resolved count=%d", len(result))
    return result
