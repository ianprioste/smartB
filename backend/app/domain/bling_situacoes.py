"""Discover and cache Bling situation (status) IDs for the Pedidos de Vendas module.

If the Bling account doesn't have the 'Situações' scope enabled, discovery
falls back to well-known standard IDs (6 = Em aberto, 9 = Atendido,
15 = Cancelado). Custom statuses like
"Pronto para Envio / Retirada" require the scope or manual configuration.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import os
import unicodedata
import re

from app.infra.logging import get_logger
from app.settings import settings

logger = get_logger(__name__)

# Bling system module ID for "Pedidos de Vendas" — standard across accounts.
VENDAS_MODULE_ID = 98310

# In-memory cache (lives for the process lifetime, which is fine for uvicorn workers).
_cached_ids: Optional[Dict[str, int]] = None
_cached_all_statuses: Optional[List[Dict]] = None

# Well-known standard Bling status IDs (work without the Situações scope).
# 12 = Cancelado is the standard Bling system ID (valor=2); 15 is a
# different status in most accounts (do NOT use 15 as cancelado fallback).
_FALLBACK_IDS: Dict[str, int] = {
    "em_aberto": 6,
    "atendido": 9,
    "cancelado": 12,
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
    def _read(key: str) -> str:
        # Prefer settings fields so values from .env are always available.
        value = getattr(settings, key, "")
        text = str(value or "").strip()
        if text:
            return text
        return os.getenv(key, "").strip()

    mapping = {
        "em_aberto": _read("BLING_STATUS_EM_ABERTO_ID"),
        "em_andamento": _read("BLING_STATUS_EM_ANDAMENTO_ID"),
        "impedido": _read("BLING_STATUS_IMPEDIDO_ID"),
        "parcialmente_entregue": _read("BLING_STATUS_PARCIALMENTE_ENTREGUE_ID"),
        "pronto_envio": _read("BLING_STATUS_PRONTO_ENVIO_ID"),
        "pronto_retirada": _read("BLING_STATUS_PRONTO_RETIRADA_ID"),
        "atendido": _read("BLING_STATUS_ATENDIDO_ID"),
        "cancelado": _read("BLING_STATUS_CANCELADO_ID"),
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


def _normalize_status_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    # Normalize common separators/abbreviations seen in Bling custom labels.
    text = text.replace("p/", "para ")
    text = text.replace(" p ", " para ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _matches_target(name: str, key: str, target: str) -> bool:
    normalized_name = _normalize_status_text(name)
    normalized_target = _normalize_status_text(target)

    if normalized_target in normalized_name:
        return True

    if key == "pronto_envio":
        return (
            "pronto" in normalized_name
            and ("envio" in normalized_name or "envi" in normalized_name)
        )

    if key == "pronto_retirada":
        return (
            "pronto" in normalized_name
            and (
                "retirada" in normalized_name
                or "retir" in normalized_name
                or "coleta" in normalized_name
            )
        )

    if key == "parcialmente_entregue":
        return "parcial" in normalized_name and "entreg" in normalized_name

    if key == "em_andamento":
        return "andamento" in normalized_name or (
            "produ" in normalized_name and "em" in normalized_name
        )

    if key == "em_aberto":
        return "aberto" in normalized_name or "pendente" in normalized_name

    if key == "atendido":
        return (
            "atendid" in normalized_name
            or "conclu" in normalized_name
            or "entreg" in normalized_name
        )

    if key == "cancelado":
        return "cancel" in normalized_name or "devolv" in normalized_name

    if key == "impedido":
        return "imped" in normalized_name

    return False


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
            if key not in result and _matches_target(name, key, target):
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
