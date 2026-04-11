"""Orders listing endpoint backed by persistent local snapshots."""
from datetime import datetime, timedelta
import asyncio
import platform
import threading
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List
from uuid import UUID

from app.infra.db import get_db, SessionLocal
from app.infra.bling_client import BlingClient, BlingAuthError, BlingAPIError
from app.infra.logging import get_logger
from app.domain.order_sync import sync_orders
from app.domain.bling_situacoes import get_bling_status_ids
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.order_snapshot_repo import OrderSnapshotRepository, parse_progress_from_sync_message
from app.repositories.item_production_note_repo import ItemProductionNoteRepository
from app.models.database import BlingOrderSnapshotModel
from app.models.schemas import ItemProductionNoteUpdateRequest, ItemProductionNoteResponse, OrderStatusUpdateRequest
from app.utils.datetime_utils import now_local

logger = get_logger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

KNOWN_STATUSES = [
    {"id": 6, "nome": "Em aberto"},
    {"id": 9, "nome": "Atendido"},
    {"id": 15, "nome": "Cancelado"},
]

# Bling situacao.valor categories: 0=Em aberto, 1=Atendido, 2=Cancelado.
_VALOR_LABEL = {0: "Em aberto", 1: "Atendido", 2: "Cancelado"}

STATUS_NAME_MAP = {
    6: "Em aberto",
    9: "Atendido",
    12: "Cancelado",
    15: "Cancelado",
}
VALID_STATUS_NAMES = {"Em aberto", "Atendido", "Cancelado"}


def _normalize_status_name(name: str | None) -> str | None:
    if not name:
        return name
    lower = name.strip().lower()
    if "atendid" in lower or "entreg" in lower:
        return "Atendido"
    if "cancel" in lower or "conclu" in lower or "devolv" in lower:
        return "Cancelado"
    if "pendente" in lower:
        return "Em aberto"
    return name


def _run_sync_in_local_background(mode: str) -> None:
    """Run order sync in a daemon thread (Windows-safe fallback when Celery is unavailable)."""
    def _worker():
        db = SessionLocal()
        client = None
        try:
            client = _make_client(db)
            if not client:
                OrderSnapshotRepository.mark_sync_failure(
                    db,
                    DEFAULT_TENANT_ID,
                    f"sync {mode}: Bling não autenticado",
                )
                db.commit()
                return
            asyncio.run(sync_orders(db, DEFAULT_TENANT_ID, client, mode=mode))
        except Exception as exc:
            logger.error("orders.local_sync_failed mode=%s error=%s", mode, str(exc), exc_info=True)
            OrderSnapshotRepository.mark_sync_failure(
                db,
                DEFAULT_TENANT_ID,
                f"sync {mode} failed: {exc}",
            )
            db.commit()
        finally:
            if client is not None:
                try:
                    asyncio.run(client.client.aclose())
                except Exception:
                    pass
            db.close()

    threading.Thread(target=_worker, daemon=True).start()


def _make_client(db: Session):
    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        return None

    def _save(access_token, refresh_token, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

    return BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )


async def _fetch_all_orders(client: BlingClient, status_ids: List[int] | None = None) -> List[Dict[str, Any]]:
    """Fetch all orders from Bling, optionally filtering by status IDs."""
    page = 1
    limit = 100
    all_orders: List[Dict[str, Any]] = []

    while True:
        params: List[tuple] = [
            ("pagina", page),
            ("limite", limit),
        ]
        for sid in (status_ids or []):
            params.append(("idsSituacoes[]", sid))

        resp = await client.get("/pedidos/vendas", params=params)
        page_data = resp.get("data", []) if isinstance(resp, dict) else []

        if not page_data:
            break

        all_orders.extend(page_data)

        if len(page_data) < limit:
            break

        page += 1
        if page > 50:
            break

    return all_orders


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _requested_status_labels(status_ids: List[int]) -> set[str]:
    labels = set()
    for sid in status_ids:
        label = STATUS_NAME_MAP.get(sid)
        if label in VALID_STATUS_NAMES:
            labels.add(label)
    return labels


def _filter_orders(orders: List[Dict], search: str) -> List[Dict]:
    """Filter orders by search text matching numero, numeroLoja, or client name."""
    if not search:
        return orders

    term = _normalize(search)
    result = []

    for o in orders:
        numero = str(o.get("numero", ""))
        numero_loja = str(o.get("numeroLoja", "") or "")
        contato = o.get("contato") or {}
        nome = contato.get("nome") or ""

        if (term in _normalize(numero)
                or term in _normalize(numero_loja)
                or term in _normalize(nome)):
            result.append(o)

    return result


def _extract_total_with_discount(order: Dict | None, fallback: Dict | None = None) -> float:
    """Extract the final charged amount, preferring total over gross items total."""
    for payload in (order, fallback):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total_final = _to_float(data.get("total"))
        if total_final > 0:
            return total_final

    for payload in (order, fallback):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total_products = _to_float(data.get("totalProdutos"))
        if total_products > 0:
            return total_products

    return 0.0


def _apply_paid_values(items: List[Dict[str, Any]], total_final: float) -> List[Dict[str, Any]]:
    """Distribute order-level discounts/surcharges proportionally across items."""
    total_items = sum(_to_float(item.get("total")) for item in items)
    factor = (total_final / total_items) if total_items > 0 else 1.0
    factor = max(0.0, factor)

    result: List[Dict[str, Any]] = []
    for item in items:
        quantity = _to_float(item.get("quantity"))
        unit_price = _to_float(item.get("unit_price"))
        total = _to_float(item.get("total"))
        paid_total = total * factor
        paid_unit_price = paid_total / quantity if quantity > 0 else unit_price * factor
        result.append({
            **item,
            "paid_unit_price": paid_unit_price,
            "paid_total": paid_total,
        })

    return result


def _extract_order_items(order_detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract items from Bling order detail payload."""
    if not order_detail:
        return []
    
    data = order_detail.get("data") if isinstance(order_detail, dict) else None
    payload = data if isinstance(data, dict) else order_detail
    
    raw_items = payload.get("itens", []) if isinstance(payload, dict) else []
    items = []
    
    for raw in raw_items:
        try:
            item = raw.get("item") if isinstance(raw, dict) and isinstance(raw.get("item"), dict) else raw
            if not isinstance(item, dict):
                continue
            
            product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
            
            sku = item.get("codigo") or product.get("codigo") or item.get("sku") or ""
            product_name = item.get("descricao") or product.get("nome") or item.get("nome") or "Produto"
            quantity = float(item.get("quantidade") or 0)
            unit_price = float(item.get("valor") or item.get("valorUnitario") or item.get("preco") or 0)
            total = float(item.get("valorTotal") or 0)
            
            if total <= 0:
                total = quantity * unit_price
            
            items.append({
                "sku": sku,
                "product_name": product_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total": total,
            })
        except Exception as e:
            logger.warning("Failed to parse order item: %s", str(e))
            continue
    
    return items


def _resolve_status_name(raw_status: Any, fallback_status_id: Any = None, persisted_status_name: str | None = None) -> str:
    """Resolve a displayable order status.

    Prefers the `valor` category (0=Em aberto, 1=Atendido, 2=Cancelado)
    which is semantically reliable even when `nome` is absent.
    """
    if isinstance(raw_status, dict):
        # Prefer valor (category) — always semantically correct.
        valor = raw_status.get("valor")
        if valor is not None:
            try:
                label = _VALOR_LABEL.get(int(valor))
                if label:
                    return label
            except (TypeError, ValueError):
                pass

        status_name = raw_status.get("nome")
        if status_name:
            return _normalize_status_name(status_name) or status_name

        status_id = raw_status.get("id") or fallback_status_id
        if status_id is not None:
            try:
                return STATUS_NAME_MAP.get(int(status_id), f"Status {status_id}")
            except (TypeError, ValueError):
                pass
        return "—"

    if persisted_status_name:
        normalized = _normalize_status_name(persisted_status_name) or persisted_status_name
        if normalized in VALID_STATUS_NAMES:
            return normalized

    if fallback_status_id is not None:
        try:
            return STATUS_NAME_MAP.get(int(fallback_status_id), f"Status {fallback_status_id}")
        except (TypeError, ValueError):
            pass

    return "—"


def _format_order(o: Dict) -> Dict:
    """Format a Bling order for the frontend."""
    situacao = o.get("situacao")
    contato = o.get("contato") or {}

    # Extract status ID and name with proper fallback
    sit_id = None
    sit_nome = "—"
    
    if isinstance(situacao, dict):
        sit_id = situacao.get("id")
        sit_nome = _resolve_status_name(situacao, sit_id)
    elif situacao is not None:
        try:
            sit_id = int(situacao)
            sit_nome = _resolve_status_name(None, sit_id)
        except (ValueError, TypeError):
            pass

    # Extract items from the detail payload
    total_final = _extract_total_with_discount(o)
    itens = _apply_paid_values(_extract_order_items(o), total_final)

    return {
        "id": o.get("id"),
        "numero": o.get("numero"),
        "numeroLoja": o.get("numeroLoja") or None,
        "data": o.get("data"),
        "cliente": contato.get("nome") or "—",
        "total": total_final,
        "situacao": sit_nome,
        "situacaoId": sit_id,
        "itens": itens,
    }


def _has_frete(detail_payload: Dict[str, Any] | None, order_payload: Dict[str, Any] | None = None) -> bool:
    """Return True if the order has shipping cost (frete)."""
    for payload in (detail_payload, order_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue
        transporte = data.get("transporte", {})
        if isinstance(transporte, dict):
            frete = _to_float(transporte.get("frete", 0))
            if frete > 0:
                return True
        taxas = data.get("taxas", {})
        if isinstance(taxas, dict):
            custo_frete = _to_float(taxas.get("custoFrete", 0))
            if custo_frete > 0:
                return True
    return False


def _inject_production_data_orders(db: Session, orders: List[Dict[str, Any]]) -> None:
    """Inject production_status, notes, production_summary into order items (global scope)."""
    note_map = ItemProductionNoteRepository.get_latest_by_sku(db, DEFAULT_TENANT_ID)
    for order in orders:
        embalado = 0
        items = order.get("itens") or []
        for item in items:
            sku_key = (item.get("sku") or "").strip().upper()
            note = note_map.get(sku_key)
            if note:
                item["production_status"] = note.production_status
                item["notes"] = note.notes
                item["event_id"] = str(note.event_id)
            else:
                item["production_status"] = "Pendente"
                item["notes"] = None
                item["event_id"] = None
            if item["production_status"] == "Embalado":
                embalado += 1
        order["production_summary"] = f"{embalado}/{len(items)} Embalado" if items else None


def _format_snapshot_order(row) -> Dict[str, Any]:
    raw_detail = row.raw_detail if isinstance(row.raw_detail, dict) else {}
    raw_order = row.raw_order if isinstance(row.raw_order, dict) else {}
    total_final = _extract_total_with_discount(raw_detail, raw_order) or float(row.total_value or 0)
    itens = _apply_paid_values(_extract_order_items(raw_detail), total_final)
    status_name = _resolve_status_name(raw_order.get("situacao"), row.status_id, row.status_name)
    if status_name == "—":
        status_name = _resolve_status_name(raw_detail.get("data", {}).get("situacao") if isinstance(raw_detail.get("data"), dict) else None, row.status_id, row.status_name)
    
    return {
        "id": int(row.bling_order_id) if row.bling_order_id is not None else None,
        "numero": row.numero,
        "numeroLoja": row.numero_loja,
        "data": row.order_date.isoformat() if row.order_date else None,
        "cliente": row.customer_name or "—",
        "total": total_final,
        "situacao": status_name or "—",
        "situacaoId": row.status_id,
        "has_frete": _has_frete(raw_detail, raw_order),
        "itens": itens,
    }


@router.get("")
async def list_orders(
    db: Session = Depends(get_db),
    search: str = Query("", description="Search by order number, client name, or Nuvemshop number"),
    statuses: str = Query("6,9,15", description="Comma-separated Bling status IDs"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """List orders from local persistent snapshot with search and status filter."""
    client = _make_client(db)
    snapshot_repo_available = True
    snapshot_count = 0
    try:
        snapshot_count = OrderSnapshotRepository.count_by_tenant(db, DEFAULT_TENANT_ID)
    except Exception as exc:
        snapshot_repo_available = False
        logger.warning("orders.snapshot_unavailable_fallback_direct_bling error=%s", str(exc))

    if snapshot_repo_available and snapshot_count == 0 and not client:
        return {
            "has_bling_auth": False,
            "data": [],
            "total": 0,
            "page": page,
            "pages": 0,
            "statuses": KNOWN_STATUSES,
            "source": "local-db",
        }

    # Parse status IDs
    status_ids = []
    for s in statuses.split(","):
        s = s.strip()
        if s.isdigit():
            status_ids.append(int(s))
    if not status_ids:
        status_ids = [6, 9, 15]

    # Merge: filtering Cancelado also includes status 12
    if 15 in status_ids and 12 not in status_ids:
        status_ids.append(12)
    requested_labels = _requested_status_labels(status_ids)

    # Fallback mode when snapshot tables are not available.
    if not snapshot_repo_available:
        if not client:
            return {
                "has_bling_auth": False,
                "data": [],
                "total": 0,
                "page": page,
                "pages": 0,
                "statuses": KNOWN_STATUSES,
                "source": "bling-direct-fallback",
            }
        try:
            all_orders = await _fetch_all_orders(client)
        except BlingAuthError:
            return {
                "has_bling_auth": False,
                "data": [],
                "total": 0,
                "page": page,
                "pages": 0,
                "statuses": KNOWN_STATUSES,
                "source": "bling-direct-fallback",
            }

        filtered = _filter_orders(all_orders, search)
        formatted = [_format_order(o) for o in filtered]
        if requested_labels:
            formatted = [o for o in formatted if (o.get("situacao") or "") in requested_labels]
        formatted.sort(key=lambda x: x.get("data") or "", reverse=True)

        total = len(formatted)
        pages = (total + limit - 1) // limit if total > 0 else 0
        start = (page - 1) * limit
        end = start + limit
        page_data = formatted[start:end]

        return {
            "has_bling_auth": True,
            "data": page_data,
            "total": total,
            "page": page,
            "pages": pages,
            "statuses": KNOWN_STATUSES,
            "source": "bling-direct-fallback",
        }

    # When local DB is empty, return immediately with a hint to trigger sync.
    if snapshot_count == 0:
        return {
            "has_bling_auth": client is not None,
            "data": [],
            "total": 0,
            "page": page,
            "pages": 0,
            "statuses": KNOWN_STATUSES,
            "source": "empty-db",
            "needs_sync": True,
        }

    rows = OrderSnapshotRepository.list_for_orders_page(db, DEFAULT_TENANT_ID, [], search)
    formatted = [_format_snapshot_order(row) for row in rows]
    if requested_labels:
        formatted = [o for o in formatted if (o.get("situacao") or "") in requested_labels]

    # Sort by date descending
    formatted.sort(key=lambda x: x.get("data") or "", reverse=True)

    # Paginate
    total = len(formatted)
    pages = (total + limit - 1) // limit if total > 0 else 0
    start = (page - 1) * limit
    end = start + limit
    page_data = formatted[start:end]

    _inject_production_data_orders(db, page_data)

    return {
        "has_bling_auth": client is not None,
        "data": page_data,
        "total": total,
        "page": page,
        "pages": pages,
        "statuses": KNOWN_STATUSES,
        "source": "local-db",
    }


@router.post("/sync/full")
async def sync_orders_full(db: Session = Depends(get_db)):
    """Dispatch full import task, preferring local background on Windows."""
    client = _make_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling não autenticado")
    OrderSnapshotRepository.mark_sync_running(
        db,
        DEFAULT_TENANT_ID,
        "full",
        "processed=0|total=0|upserted=0|failed=0|queued=1",
    )
    db.commit()

    # Windows fallback: run in-process background thread to avoid Celery worker issues.
    if platform.system() == "Windows":
        _run_sync_in_local_background("full")
        return {
            "ok": True,
            "status": "queued",
            "runner": "local-background",
            "message": "Importação full iniciada em background local (sem Celery).",
        }

    from app.workers.tasks import sync_orders_full_task
    sync_orders_full_task.delay()
    return {
        "ok": True,
        "status": "queued",
        "runner": "celery",
        "message": "Importação full iniciada em background. Aguarde alguns minutos.",
    }


@router.post("/sync/incremental")
async def sync_orders_incremental(db: Session = Depends(get_db)):
    """Dispatch incremental import task, preferring local background on Windows."""
    client = _make_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling não autenticado")
    OrderSnapshotRepository.mark_sync_running(
        db,
        DEFAULT_TENANT_ID,
        "incremental",
        "processed=0|total=0|upserted=0|failed=0|queued=1",
    )
    db.commit()

    if platform.system() == "Windows":
        _run_sync_in_local_background("incremental")
        return {
            "ok": True,
            "status": "queued",
            "runner": "local-background",
            "message": "Sincronização incremental iniciada em background local (sem Celery).",
        }

    from app.workers.tasks import sync_orders_incremental_task
    sync_orders_incremental_task.delay()
    return {
        "ok": True,
        "status": "queued",
        "runner": "celery",
        "message": "Sincronização incremental iniciada em background.",
    }


@router.get("/sync/status")
async def sync_orders_status(db: Session = Depends(get_db)):
    """Sync health/status endpoint for local order snapshot monitoring."""
    try:
        state = OrderSnapshotRepository.get_sync_state(db, DEFAULT_TENANT_ID)
        stats = OrderSnapshotRepository.get_snapshot_stats(db, DEFAULT_TENANT_ID)
    except Exception as exc:
        logger.warning("orders.sync_status_snapshot_unavailable error=%s", str(exc))
        return {
            "ok": False,
            "source": "snapshot-unavailable",
            "snapshot": {
                "total_orders": 0,
                "latest_order_date": None,
                "latest_imported_at": None,
                "latest_updated_at": None,
            },
            "sync": {
                "last_full_sync_at": None,
                "last_incremental_sync_at": None,
                "last_successful_sync_at": None,
                "last_sync_status": "unavailable",
                "last_sync_message": f"Snapshot indisponível: {exc}",
                "progress": {
                    "mode": None,
                    "processed": 0,
                    "total": 0,
                    "upserted": 0,
                    "failed": 0,
                    "percent": 0,
                },
            },
        }

    sync_status = state.last_sync_status if state else "never"
    sync_message = state.last_sync_message if state else "No sync executed yet"
    progress = parse_progress_from_sync_message(sync_message)

    # Detect stale queued/running state (worker down or queue not consumed).
    if state and sync_status == "running":
        _now = now_local()
        _updated = state.updated_at or _now
        # Ensure both are aware or both are naive before subtracting
        if _updated.tzinfo is None:
            _updated = _updated.replace(tzinfo=_now.tzinfo)
        age = _now - _updated
        if progress.get("processed", 0) == 0 and progress.get("total", 0) == 0 and age > timedelta(seconds=300):
            sync_status = "error"
            sync_message = "Sincronização sem progresso inicial por 5 minutos. Verifique backend/credenciais Bling/rede."
            progress = {
                "mode": progress.get("mode"),
                "processed": 0,
                "total": 0,
                "upserted": 0,
                "failed": 0,
                "percent": 0,
            }

    return {
        "ok": True,
        "source": "local-db",
        "snapshot": {
            "total_orders": stats.get("total_orders", 0),
            "latest_order_date": stats.get("latest_order_date").isoformat() if stats.get("latest_order_date") else None,
            "latest_imported_at": stats.get("latest_imported_at").isoformat() if stats.get("latest_imported_at") else None,
            "latest_updated_at": stats.get("latest_updated_at").isoformat() if stats.get("latest_updated_at") else None,
        },
        "sync": {
            "last_full_sync_at": state.last_full_sync_at.isoformat() if state and state.last_full_sync_at else None,
            "last_incremental_sync_at": state.last_incremental_sync_at.isoformat() if state and state.last_incremental_sync_at else None,
            "last_successful_sync_at": state.last_successful_sync_at.isoformat() if state and state.last_successful_sync_at else None,
            "last_sync_status": sync_status,
            "last_sync_message": sync_message,
            "progress": progress,
        },
    }


@router.get("/diagnose/{order_numero}")
async def diagnose_order(order_numero: str, db: Session = Depends(get_db)):
    """Diagnose a specific order by numero, showing stored status and Bling status."""
    # Convert to int
    try:
        order_numero_int = int(order_numero)
    except ValueError:
        raise HTTPException(status_code=400, detail="order_numero deve ser um número inteiro")
    
    # Get from local DB
    local = None
    try:
        local = (
            db.query(BlingOrderSnapshotModel)
            .filter(
                BlingOrderSnapshotModel.tenant_id == DEFAULT_TENANT_ID,
                BlingOrderSnapshotModel.numero == order_numero_int,
            )
            .first()
        )
    except Exception as exc:
        logger.warning("diagnose_order local_fetch_failed order_numero=%s error=%s", order_numero, str(exc))

    # Get from Bling API
    bling_data = None
    try:
        client = _make_client(db)
        if client:
            orders = await _fetch_all_orders(client, [6, 9, 12, 15])
            for o in orders:
                if o.get("numero") == order_numero_int:
                    bling_data = o
                    break
    except Exception as exc:
        logger.warning("diagnose_order bling_fetch_failed order_numero=%s error=%s", order_numero, str(exc))

    return {
        "order_numero": order_numero_int,
        "local_db": {
            "found": local is not None,
            "bling_order_id": local.bling_order_id if local else None,
            "status_id": local.status_id if local else None,
            "status_name": local.status_name if local else None,
            "total_value": local.total_value if local else None,
            "raw_order_situacao": local.raw_order.get("situacao") if local and local.raw_order else None,
        } if local else None,
        "bling_api": {
            "found": bling_data is not None,
            "id": bling_data.get("id") if bling_data else None,
            "raw_situacao": bling_data.get("situacao") if bling_data else None,
        } if bling_data else None,
        "expected_mapping": KNOWN_STATUSES,
    }


@router.put("/items/{sku}/production", response_model=ItemProductionNoteResponse)
async def update_order_item_production(
    sku: str,
    body: ItemProductionNoteUpdateRequest,
    db: Session = Depends(get_db),
):
    """Upsert production status for a SKU from the global orders page.

    Uses the event_id from the most recent existing note for this SKU,
    or falls back to the most recent active event.
    """
    from app.models.database import SalesEventModel

    norm_sku = sku.strip().upper()

    # Try to find existing note for this SKU (latest).
    note_map = ItemProductionNoteRepository.get_latest_by_sku(db, DEFAULT_TENANT_ID)
    existing = note_map.get(norm_sku)

    if existing:
        event_id = existing.event_id
    else:
        # Fallback: use the most recent event.
        latest_event = (
            db.query(SalesEventModel)
            .filter(SalesEventModel.tenant_id == DEFAULT_TENANT_ID)
            .order_by(SalesEventModel.start_date.desc())
            .first()
        )
        if not latest_event:
            raise HTTPException(status_code=400, detail="Nenhuma campanha encontrada para associar a nota de produção")
        event_id = latest_event.id

    row = ItemProductionNoteRepository.upsert(
        db, DEFAULT_TENANT_ID, event_id, norm_sku, body.production_status, body.notes,
        bling_order_id=body.bling_order_id,
    )
    return ItemProductionNoteResponse(
        sku=row.sku, production_status=row.production_status, notes=row.notes,
        bling_order_id=row.bling_order_id,
    )


@router.put("/orders/{order_id}/status")
async def update_order_bling_status(
    order_id: int,
    body: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a Bling order status (e.g. mark as Atendido) from the global orders page."""
    client = _make_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling não autenticado")

    sit_ids = await get_bling_status_ids(client)

    target_key = body.situacao.strip().lower()
    target_id = None
    if "atendido" in target_key:
        target_id = sit_ids.get("atendido")
    elif "envio" in target_key:
        target_id = sit_ids.get("pronto_envio")
    elif "retirada" in target_key:
        target_id = sit_ids.get("pronto_retirada")

    if not target_id:
        raise HTTPException(status_code=400, detail=f"Situação '{body.situacao}' não encontrada no Bling")

    try:
        await client.patch(f"/pedidos/vendas/{order_id}/situacoes/{target_id}", {})
    except BlingAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao atualizar status no Bling: {exc}")

    # Update local snapshot.
    snapshot = db.query(BlingOrderSnapshotModel).filter(
        BlingOrderSnapshotModel.bling_order_id == order_id,
        BlingOrderSnapshotModel.tenant_id == DEFAULT_TENANT_ID,
    ).first()
    if snapshot:
        snapshot.status_id = target_id
        snapshot.status_name = body.situacao
        db.commit()

    return {"ok": True, "order_id": order_id, "new_status": body.situacao}
