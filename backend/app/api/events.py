"""Sales events API: create events and view sales filtered by event products."""
from typing import Any, Dict, List
from uuid import UUID
import re
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingAuthError, BlingAPIError
from app.infra.logging import get_logger
from app.domain.order_local_cache import get_cached_order_detail, warm_order_details
from app.domain.bling_situacoes import get_bling_status_ids
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.order_snapshot_repo import OrderSnapshotRepository
from app.repositories.order_tag_repo import OrderTagRepository, OrderTagSchemaError
from app.repositories.sales_event_repo import SalesEventRepository
from app.repositories.item_production_note_repo import ItemProductionNoteRepository
from app.repositories.sync_scope_version_repo import (
    SyncScopeVersionRepository,
    SCOPE_ORDERS_GLOBAL,
    scope_event_sales,
)
from app.models.schemas import (
    SalesEventCreateRequest,
    SalesEventUpdateRequest,
    SalesEventResponse,
    SalesEventListItemResponse,
    SalesEventProductResponse,
    EventMatchedItemResponse,
    EventOrderResponse,
    EventSalesSummaryResponse,
    EventSalesResponse,
    ItemProductionNoteUpdateRequest,
    ItemProductionNoteResponse,
    OrderStatusUpdateRequest,
    OrderTagAssignRequest,
)

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger(__name__)

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Unified sales-order status labels used across Orders and Event Sales pages.
# Bling situacao.valor categories: 0=Em aberto, 1=Atendido, 2=Cancelado.
_VALOR_LABEL = {0: "Em aberto", 1: "Atendido", 2: "Cancelado"}

# Fallback mapping by known status IDs (used when 'valor' is unavailable).
_ATENDIDO_IDS = {9}
_CANCELADO_IDS = {12, 15}

STATUS_ID_NAME_MAP = {**{sid: "Atendido" for sid in _ATENDIDO_IDS}, **{sid: "Cancelado" for sid in _CANCELADO_IDS}}


def _field_was_provided(model, field_name: str) -> bool:
    fields_set = getattr(model, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(model, "__fields_set__", set())
    return field_name in fields_set


def _parse_since_cursor(since: str | None) -> datetime:
    if not since:
        return datetime.utcnow() - timedelta(seconds=30)
    text = since.strip()
    if not text:
        return datetime.utcnow() - timedelta(seconds=30)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Cursor 'since' inválido")


def _has_frete(detail_payload: Dict[str, Any] | None, order_payload: Dict[str, Any] | None = None) -> bool:
    """Return True if the order has shipping cost (frete), meaning it's a delivery."""
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


def _inject_production_data(db: Session, event_id: UUID, filtered_orders: list) -> list:
    """Populate production_status, notes, and production_summary on order items."""
    notes = ItemProductionNoteRepository.get_all_for_event(db, DEFAULT_TENANT_ID, event_id)
    note_map = {}
    sku_fallback_map = {}
    for n in notes:
        sku_key = n.sku.strip().upper()
        note_map[(sku_key, n.bling_order_id)] = n
        if n.bling_order_id is None:
            sku_fallback_map[sku_key] = n
    for order in filtered_orders:
        embalado_count = 0
        total_items = len(order.matched_items)
        order_bling_id = order.id  # bling_order_id stored as order.id
        for item in order.matched_items:
            sku_key = (item.sku or "").strip().upper()
            note = note_map.get((sku_key, order_bling_id)) or sku_fallback_map.get(sku_key)
            if note:
                item.production_status = note.production_status
                item.notes = note.notes
            if item.production_status == "Embalado":
                embalado_count += 1
        if total_items > 0:
            order.production_summary = f"{embalado_count}/{total_items} Embalado"
    return filtered_orders


def _inject_event_tags(db: Session, event_id: UUID, filtered_orders: List[EventOrderResponse]) -> None:
    order_ids = [int(order.id) for order in filtered_orders if order.id is not None]
    tag_map = OrderTagRepository.get_assignments_map(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        scope_key="event",
        event_id=event_id,
        bling_order_ids=order_ids,
    )
    for order in filtered_orders:
        tags = tag_map.get(int(order.id), []) if order.id is not None else []
        order.tags = tags
        order.tag = tags[0] if tags else None


def _normalize_sku(value: Any) -> str:
    return str(value or "").strip().upper()


def _canonical_sku(value: Any) -> str:
    """Normalize SKU for resilient matching (ignore case and separators)."""
    raw = str(value or "").strip().casefold()
    return re.sub(r"[^a-z0-9]", "", raw)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0

def _extract_total_with_discount(primary_payload: Dict[str, Any] | None, fallback_payload: Dict[str, Any] | None = None) -> float:
    for payload in (primary_payload, fallback_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total_final = _to_float(data.get("total"))
        if total_final > 0:
            return total_final

    for payload in (primary_payload, fallback_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total_products = _to_float(data.get("totalProdutos"))
        if total_products > 0:
            return total_products

    return 0.0


def _extract_customer_email(primary_payload: Dict[str, Any] | None, fallback_payload: Dict[str, Any] | None = None) -> str | None:
    for payload in (primary_payload, fallback_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue

        contato = data.get("contato") if isinstance(data.get("contato"), dict) else {}
        cliente = data.get("cliente") if isinstance(data.get("cliente"), dict) else {}

        candidates = [
            contato.get("email"),
            cliente.get("email"),
            data.get("email"),
            data.get("emailContato"),
        ]

        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and "@" in text:
                return text

    return None


def _to_optional_int(value: Any) -> int | None:
    """Best-effort integer conversion for inconsistent Bling payloads."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)

    match = re.search(r"-?\d+", text)
    if match:
        try:
            return int(match.group(0))
        except Exception:
            return None

    return None


def _normalize_status_label(text: Any) -> str:
    raw = str(text or "").strip()
    if not raw:
        return "Em aberto"
    lower = raw.casefold()
    if "atendid" in lower or "conclu" in lower or "entreg" in lower:
        return "Atendido"
    if "cancel" in lower or "devolv" in lower:
        return "Cancelado"
    return "Em aberto"


def _status_to_text(raw_status: Any, fallback_status_id: Any = None) -> str:
    """Normalize Bling order status to a safe, always-string value.

    Prefers the `valor` category field (0=Em aberto, 1=Atendido, 2=Cancelado)
    which is always reliable, even when `nome` is absent.
    """
    if isinstance(raw_status, dict):
        # Prefer valor (category) — it's always semantically correct.
        valor = _to_optional_int(raw_status.get("valor"))
        if valor is not None and valor in _VALOR_LABEL:
            return _VALOR_LABEL[valor]

        name = raw_status.get("nome")
        if name is not None:
            return _normalize_status_label(name)

        status_id = _to_optional_int(raw_status.get("id"))
        if status_id is not None:
            return STATUS_ID_NAME_MAP.get(status_id, "Em aberto")

    status_id = _to_optional_int(fallback_status_id if fallback_status_id is not None else raw_status)
    if status_id is not None:
        return STATUS_ID_NAME_MAP.get(status_id, "Em aberto")

    return _normalize_status_label(raw_status)


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


def _map_event_response(db: Session, event) -> SalesEventResponse:
    products = SalesEventRepository.list_products(db, event.id)
    return SalesEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        name=event.name,
        start_date=event.start_date,
        end_date=event.end_date,
        created_at=event.created_at,
        updated_at=event.updated_at,
        products=[
            SalesEventProductResponse(
                id=p.id,
                bling_product_id=p.bling_product_id,
                sku=p.sku,
                product_name=p.product_name,
                created_at=p.created_at,
            )
            for p in products
        ],
    )


async def _expand_products_with_children(
    db: Session,
    products: List[dict],
) -> List[dict]:
    """If a selected product is a parent, include all children SKUs in the event."""
    client = _make_client(db)
    if not client:
        return products

    result: List[dict] = []
    seen_skus: set[str] = set()

    for product in products:
        sku = _normalize_sku(product.get("sku"))
        if sku and sku not in seen_skus:
            result.append(
                {
                    "bling_product_id": product.get("bling_product_id"),
                    "sku": sku,
                    "product_name": product.get("product_name"),
                }
            )
            seen_skus.add(sku)

        product_id = product.get("bling_product_id")
        if not product_id:
            continue

        try:
            detail = await client.get(f"/produtos/{product_id}")
            data = detail.get("data") if isinstance(detail, dict) else None
            payload = data if isinstance(data, dict) else detail

            variations = payload.get("variacoes", []) if isinstance(payload, dict) else []
            if not isinstance(variations, list):
                continue

            for variation in variations:
                child_sku = _normalize_sku(
                    variation.get("codigo")
                    or variation.get("item", {}).get("codigo")
                )
                if not child_sku or child_sku in seen_skus:
                    continue

                result.append(
                    {
                        "bling_product_id": variation.get("id"),
                        "sku": child_sku,
                        "product_name": variation.get("nome") or variation.get("item", {}).get("nome") or child_sku,
                    }
                )
                seen_skus.add(child_sku)
        except Exception:
            # Keep original selection if expansion fails for one product.
            continue

    return result


async def _expand_selected_products_for_sales(
    db: Session,
    products: List[SalesEventProductResponse],
) -> tuple[set[str], set[int]]:
    """Expand selected products at read time to include children of parent items."""
    base_products = [
        {
            "bling_product_id": p.bling_product_id,
            "sku": p.sku,
            "product_name": p.product_name,
        }
        for p in products
    ]
    expanded = await _expand_products_with_children(db, base_products)
    skus = {_normalize_sku(p.get("sku")) for p in expanded if _normalize_sku(p.get("sku"))}
    ids = {
        int(p.get("bling_product_id"))
        for p in expanded
        if p.get("bling_product_id") is not None
    }
    return skus, ids


async def _fetch_orders_for_period(
    client: BlingClient,
    start_date: str,
    end_date: str,
    selected_product_ids: set[int] | None = None,
) -> List[Dict[str, Any]]:
    """Fetch all orders in date range, paginating through Bling results."""
    async def _fetch_with_dates(
        date_from: str,
        date_to: str,
        product_ids: set[int] | None,
    ) -> List[Dict[str, Any]]:
        page = 1
        limit = 100
        all_orders: List[Dict[str, Any]] = []
        use_product_filter = bool(product_ids)

        while True:
            params: Dict[str, Any] = {
                "dataInicial": date_from,
                "dataFinal": date_to,
                "pagina": page,
                "limite": limit,
            }
            if use_product_filter and product_ids:
                params["idsProdutos[]"] = sorted(product_ids)

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

    product_ids = {pid for pid in (selected_product_ids or set()) if pid is not None}

    try:
        orders = await _fetch_with_dates(start_date, end_date, product_ids)
    except BlingAPIError as exc:
        # Some Bling accounts may reject product filters on /pedidos/vendas.
        if product_ids:
            logger.warning(
                "event_sales_orders_product_filter_unsupported fallback=true error=%s",
                str(exc),
            )
            orders = await _fetch_with_dates(start_date, end_date, None)
        else:
            raise

    if orders:
        return orders

    # Fallback for Bling accounts expecting DD/MM/YYYY params.
    try:
        y1, m1, d1 = start_date.split("-")
        y2, m2, d2 = end_date.split("-")
        start_br = f"{d1}/{m1}/{y1}"
        end_br = f"{d2}/{m2}/{y2}"
        try:
            return await _fetch_with_dates(start_br, end_br, product_ids)
        except BlingAPIError as exc:
            if product_ids:
                logger.warning(
                    "event_sales_orders_product_filter_unsupported_br fallback=true error=%s",
                    str(exc),
                )
                return await _fetch_with_dates(start_br, end_br, None)
            raise
    except Exception:
        return []


def _match_event_items(
    order_items: List[Dict[str, Any]],
    selected_skus_canonical: set[str],
    selected_product_ids: set[int],
) -> List[Dict[str, Any]]:
    """Return only items that belong to the event (SKU or product id match)."""
    matched: List[Dict[str, Any]] = []
    for item in order_items:
        product_id = item.get("product_id")
        item_sku = item.get("sku")
        sku_match = _canonical_sku(item_sku) in selected_skus_canonical if item_sku else False
        id_match = product_id in selected_product_ids if product_id is not None else False
        if sku_match or id_match:
            matched.append(item)
    return matched


def _calculate_proportional_value(
    total_items_matched: float,
    total_order_items: float,
    total_order_final: float,
) -> float:
    """Calculate the value really paid for matched items, considering discounts/surcharges.
    
    If order total_items = 1000, but total_final = 900 (10% discount),
    and matched items = 600, then:
    proportion = 600 / 1000 = 0.6
    value_paid = 900 * 0.6 = 540
    """
    if total_order_items <= 0:
        return total_items_matched
    
    # Avoid division by zero
    proportion = min(1.0, max(0.0, total_items_matched / total_order_items))
    return total_order_final * proportion


def _extract_order_items(order_detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = order_detail.get("data") if isinstance(order_detail, dict) else None
    payload = data if isinstance(data, dict) else order_detail

    raw_items = payload.get("itens", []) if isinstance(payload, dict) else []
    parsed_items: List[Dict[str, Any]] = []

    for raw in raw_items:
        try:
            item = raw.get("item") if isinstance(raw, dict) and isinstance(raw.get("item"), dict) else raw
            if not isinstance(item, dict):
                continue

            product = item.get("produto") if isinstance(item.get("produto"), dict) else {}
            raw_product_id = (
                product.get("id")
                or item.get("idProduto")
                or item.get("produtoId")
                or item.get("idProdutoBling")
            )
            product_id = _to_optional_int(raw_product_id)

            sku = _normalize_sku(
                item.get("codigo")
                or product.get("codigo")
                or item.get("sku")
                or item.get("codigoItem")
            )
            if not sku and product_id is None:
                continue

            quantity = _to_float(item.get("quantidade"))
            unit_price = _to_float(item.get("valor") or item.get("valorUnitario") or item.get("preco"))
            total = _to_float(item.get("valorTotal"))
            if total <= 0:
                total = quantity * unit_price

            parsed_items.append(
                {
                    "sku": sku,
                    "product_id": product_id,
                    "product_name": str(
                        item.get("descricao")
                        or product.get("nome")
                        or item.get("nome")
                        or "Produto"
                    ),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": total,
                    "valor_unitario_original": unit_price,
                }
            )
        except Exception:
            # Skip malformed item without breaking entire event sales response.
            continue

    return parsed_items


@router.post("", response_model=SalesEventResponse)
async def create_event(
    request: SalesEventCreateRequest,
    db: Session = Depends(get_db),
):
    normalized_products = []
    seen_skus = set()

    for product in request.products:
        sku = _normalize_sku(product.sku)
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        normalized_products.append(
            {
                "bling_product_id": product.bling_product_id,
                "sku": sku,
                "product_name": product.product_name,
            }
        )

    if not normalized_products:
        raise HTTPException(status_code=400, detail="Selecione ao menos um produto válido para o evento")

    normalized_products = await _expand_products_with_children(db, normalized_products)

    event = SalesEventRepository.create(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        name=request.name.strip(),
        start_date=request.start_date,
        end_date=request.end_date,
        products=normalized_products,
    )

    return _map_event_response(db, event)


@router.put("/{event_id}", response_model=SalesEventResponse)
async def update_event(
    event_id: UUID,
    request: SalesEventUpdateRequest,
    db: Session = Depends(get_db),
):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    normalized_products = []
    seen_skus = set()

    for product in request.products:
        sku = _normalize_sku(product.sku)
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        normalized_products.append(
            {
                "bling_product_id": product.bling_product_id,
                "sku": sku,
                "product_name": product.product_name,
            }
        )

    if not normalized_products:
        raise HTTPException(status_code=400, detail="Selecione ao menos um produto válido para o evento")

    normalized_products = await _expand_products_with_children(db, normalized_products)

    updated = SalesEventRepository.update(
        db=db,
        event=event,
        name=request.name.strip(),
        start_date=request.start_date,
        end_date=request.end_date,
        products=normalized_products,
    )

    return _map_event_response(db, updated)


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: UUID, db: Session = Depends(get_db)):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    SalesEventRepository.delete(db, event)
    return None


@router.patch("/{event_id}/toggle-status")
async def toggle_event_status(event_id: UUID, db: Session = Depends(get_db)):
    """Toggle event active status between active and inactive."""
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    event.is_active = not event.is_active
    db.commit()
    db.refresh(event)

    return {
        "ok": True,
        "id": event.id,
        "name": event.name,
        "is_active": event.is_active,
    }


@router.get("", response_model=List[SalesEventListItemResponse])
async def list_events(db: Session = Depends(get_db)):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy import text

    # Primary path: full ORM query including is_active column.
    try:
        events = SalesEventRepository.list_by_tenant(db, DEFAULT_TENANT_ID)
    except OperationalError as exc:
        # Fallback: is_active column may not exist yet (pending migration).
        # Query without that column and default to True so the page loads normally.
        logger.warning("list_events_is_active_missing – running fallback query. error=%s", str(exc)[:200])
        db.rollback()
        try:
            rows = db.execute(
                text(
                    "SELECT id, name, start_date, end_date, created_at "
                    "FROM sales_events WHERE tenant_id = :tid ORDER BY created_at DESC"
                ),
                {"tid": str(DEFAULT_TENANT_ID).replace("-", "")},
            ).fetchall()
        except Exception:
            rows = db.execute(
                text(
                    "SELECT id, name, start_date, end_date, created_at "
                    "FROM sales_events WHERE tenant_id = :tid ORDER BY created_at DESC"
                ),
                {"tid": str(DEFAULT_TENANT_ID)},
            ).fetchall()

        class _PlainEvent:
            __slots__ = ("id", "name", "start_date", "end_date", "created_at", "is_active")

            def __init__(self, row):
                self.id = row[0]
                self.name = row[1]
                self.start_date = row[2]
                self.end_date = row[3]
                self.created_at = row[4]
                self.is_active = True

        events = [_PlainEvent(r) for r in rows]

    results: List[SalesEventListItemResponse] = []

    for event in events:
        try:
            products = SalesEventRepository.list_products(db, event.id)
        except Exception:
            products = []
        # Defensive casting: guard against NULL is_active from legacy rows.
        is_active = True if event.is_active is None else bool(event.is_active)
        if event.is_active is None:
            logger.warning("event_list_null_is_active event_id=%s defaulting_true", str(event.id))
        results.append(
            SalesEventListItemResponse(
                id=event.id,
                name=event.name,
                start_date=event.start_date,
                end_date=event.end_date,
                products_count=int(len(products)),
                is_active=is_active,
                created_at=event.created_at,
            )
        )

    # Sort by end_date DESC, then start_date DESC
    results.sort(key=lambda x: (x.end_date, x.start_date), reverse=True)
    return results


@router.get("/{event_id}", response_model=SalesEventResponse)
async def get_event(event_id: UUID, db: Session = Depends(get_db)):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    return _map_event_response(db, event)


@router.get("/{event_id}/sales", response_model=EventSalesResponse)
async def get_event_sales(event_id: UUID, enrich_emails: bool = Query(default=False), db: Session = Depends(get_db)):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    event_response = _map_event_response(db, event)
    # Prefer persisted event products to avoid extra API calls on every read.
    selected_skus = {
        _normalize_sku(p.sku)
        for p in event_response.products
        if _normalize_sku(p.sku)
    }
    selected_skus_canonical = {_canonical_sku(sku) for sku in selected_skus if sku}
    selected_product_ids = {
        pid
        for pid in (_to_optional_int(p.bling_product_id) for p in event_response.products)
        if pid is not None
    }

    # Primary source: local persistent DB snapshots.
    start_dt = datetime.combine(event.start_date, time.min)
    end_dt = datetime.combine(event.end_date, time.max)
    snapshot_rows = OrderSnapshotRepository.list_for_period(db, DEFAULT_TENANT_ID, start_dt, end_dt)

    if snapshot_rows:
        logger.info(
            "event_sales_local_db_start event_id=%s orders_in_period=%s products=%s expanded_skus=%s expanded_ids=%s",
            str(event_id),
            len(snapshot_rows),
            len(event_response.products),
            len(selected_skus_canonical),
            len(selected_product_ids),
        )

        filtered_order_map: dict[Any, EventOrderResponse] = {}
        order_contact_id_map: dict[str, int] = {}
        matched_items_count = 0
        total_matched = 0.0

        for row in snapshot_rows:
            detail_payload = row.raw_detail if isinstance(row.raw_detail, dict) else {}
            order_payload = row.raw_order if isinstance(row.raw_order, dict) else {}

            order_items = _extract_order_items(detail_payload)
            if not order_items:
                order_items = _extract_order_items(order_payload)

            matched = _match_event_items(order_items, selected_skus_canonical, selected_product_ids)
            if not matched:
                continue

            # Calculate value with discount consideration
            total_items_sum = sum(item.get("total", 0) for item in order_items)
            total_matched_items_sum = sum(item.get("total", 0) for item in matched)
            total_order_final = _extract_total_with_discount(detail_payload, order_payload) or _to_float(row.total_value)
            
            # Calculate the overall discount factor to apply to each matched item
            discount_factor = (total_order_final / total_items_sum) if total_items_sum > 0 else 1.0
            
            # Create matched_items with paid values calculated
            matched_items = []
            for item in matched:
                paid_total = _to_float(item.get("total", 0)) * discount_factor
                paid_unit_price = _to_float(item.get("unit_price", 0)) * discount_factor
                matched_items.append(EventMatchedItemResponse(
                    sku=item.get("sku", ""),
                    product_name=item.get("product_name", ""),
                    quantity=_to_float(item.get("quantity", 0)),
                    unit_price=_to_float(item.get("unit_price", 0)),
                    total=_to_float(item.get("total", 0)),
                    paid_unit_price=paid_unit_price,
                    paid_total=paid_total,
                ))
            
            order_total_matched = _calculate_proportional_value(
                total_matched_items_sum,
                total_items_sum,
                total_order_final
            )

            matched_items_count += len(matched_items)
            total_matched += order_total_matched

            key = row.bling_order_id or row.numero
            # Priorize status persistido localmente no snapshot quando disponível.
            situacao_text = _status_to_text(row.status_name, row.status_id)

            if situacao_text == "Cancelado":
                continue

            filtered_order_map[key] = EventOrderResponse(
                id=int(row.bling_order_id) if row.bling_order_id is not None else None,
                numero=row.numero,
                numero_loja=row.numero_loja,
                data=row.order_date.isoformat() if row.order_date else None,
                cliente=row.customer_name or "—",
                email=row.customer_email or _extract_customer_email(detail_payload, order_payload),
                situacao=situacao_text,
                total_order=total_order_final,
                total_matched=order_total_matched,
                has_frete=_has_frete(detail_payload, order_payload),
                matched_items=matched_items,
            )
            parsed_contact_id = _to_optional_int(row.customer_contact_id)
            if parsed_contact_id is not None:
                order_contact_id_map[str(key)] = parsed_contact_id

        filtered_orders = list(filtered_order_map.values())
        _inject_production_data(db, event_id, filtered_orders)
        try:
            _inject_event_tags(db, event_id, filtered_orders)
        except Exception as exc:
            logger.warning("event_tags_injection_failed event_id=%s error=%s", str(event_id), str(exc))

        # On-demand email enrichment: fetch contact emails for orders still missing them.
        if enrich_emails:
            client = _make_client(db)
            if client:
                missing = [o for o in filtered_orders if not o.email]
                seen_contacts: dict[int, str] = {}
                newly_resolved: dict[int, str] = {}
                for order in missing:
                    lookup_key = str(order.id or order.numero or "")
                    cid = order_contact_id_map.get(lookup_key)
                    if not cid:
                        continue
                    if cid in seen_contacts:
                        order.email = seen_contacts[cid]
                        continue
                    try:
                        payload = await client.get(f"/contatos/{cid}")
                        data = payload.get("data") or {}
                        contato = data.get("contato") if isinstance(data.get("contato"), dict) else {}
                        email = (
                            contato.get("email")
                            or data.get("email")
                            or data.get("emailContato")
                        )
                        email = str(email or "").strip() or None
                        if email:
                            seen_contacts[cid] = email
                            newly_resolved[cid] = email
                            order.email = email
                    except Exception as exc:
                        logger.warning(
                            "enrich_email_failed order_id=%s contact_id=%s error=%s",
                            order.id, cid, str(exc)
                        )
                if newly_resolved:
                    try:
                        OrderSnapshotRepository.apply_customer_emails_by_contact_id(
                            db, DEFAULT_TENANT_ID, newly_resolved
                        )
                        db.commit()
                    except Exception as exc:
                        logger.warning("enrich_email_persist_failed error=%s", str(exc))
                        db.rollback()

        logger.info(
            "event_sales_local_db_done event_id=%s matched_orders=%s matched_items=%s total_matched=%.2f",
            str(event_id),
            len(filtered_orders),
            matched_items_count,
            total_matched,
        )

        return EventSalesResponse(
            event=event_response,
            summary=EventSalesSummaryResponse(
                orders_count=len(filtered_orders),
                matched_items_count=matched_items_count,
                total_matched=total_matched,
            ),
            orders=filtered_orders,
        )

    client = _make_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling não autenticado")

    try:
        orders = await _fetch_orders_for_period(
            client,
            event.start_date.strftime("%Y-%m-%d"),
            event.end_date.strftime("%Y-%m-%d"),
            selected_product_ids,
        )
        logger.info(
            "event_sales_filter_start event_id=%s orders_in_period=%s products=%s expanded_skus=%s expanded_ids=%s",
            str(event_id),
            len(orders),
            len(event_response.products),
            len(selected_skus_canonical),
            len(selected_product_ids),
        )

        filtered_orders: List[EventOrderResponse] = []
        matched_items_count = 0
        total_matched = 0.0
        local_fallback_used = 0

        # Local-first strategy:
        # 1) Warm missing details once.
        # 2) Filter strictly from locally cached full order details.
        filtered_order_map: dict[Any, EventOrderResponse] = {}
        cache_hits, fetched, failed = await warm_order_details(client, orders, max_concurrency=3)
        logger.info(
            "event_sales_local_warm_done orders_in_period=%s cache_hits=%s fetched=%s failed=%s",
            len(orders),
            cache_hits,
            fetched,
            failed,
        )

        for order in orders:
            order_id = order.get("id")
            detail = get_cached_order_detail(order_id)
            if detail is None:
                logger.warning(
                    "event_sales_cached_detail_missing event_id=%s order_id=%s",
                    str(event_id),
                    str(order_id),
                )
                order_items = _extract_order_items(order)
                local_fallback_used += 1
            else:
                order_items = _extract_order_items(detail)
                if not order_items:
                    # Local cache may hold sparse data for some orders; fallback to list payload.
                    order_items = _extract_order_items(order)
                    local_fallback_used += 1

            matched = _match_event_items(order_items, selected_skus_canonical, selected_product_ids)

            if not matched:
                continue

            # Calculate value with discount consideration
            total_items_sum = sum(item.get("total", 0) for item in order_items)
            total_matched_items_sum = sum(item.get("total", 0) for item in matched)
            total_order_final = _extract_total_with_discount(detail, order)
            
            # Calculate the overall discount factor to apply to each matched item
            discount_factor = (total_order_final / total_items_sum) if total_items_sum > 0 else 1.0
            
            # Create matched_items with paid values calculated
            matched_items = []
            for item in matched:
                paid_total = _to_float(item.get("total", 0)) * discount_factor
                paid_unit_price = _to_float(item.get("unit_price", 0)) * discount_factor
                matched_items.append(EventMatchedItemResponse(
                    sku=item.get("sku", ""),
                    product_name=item.get("product_name", ""),
                    quantity=_to_float(item.get("quantity", 0)),
                    unit_price=_to_float(item.get("unit_price", 0)),
                    total=_to_float(item.get("total", 0)),
                    paid_unit_price=paid_unit_price,
                    paid_total=paid_total,
                ))
            
            order_total_matched = _calculate_proportional_value(
                total_matched_items_sum,
                total_items_sum,
                total_order_final
            )

            matched_items_count += len(matched_items)
            total_matched += order_total_matched

            situacao = order.get("situacao") if isinstance(order.get("situacao"), dict) else {}
            key = order.get("id") or order.get("numero")
            situacao_text = _status_to_text(situacao if isinstance(situacao, dict) else order.get("situacao"))

            if situacao_text == "Cancelado":
                continue

            filtered_order_map[key] = EventOrderResponse(
                id=order.get("id"),
                numero=order.get("numero"),
                numero_loja=order.get("numeroLoja"),
                data=order.get("data"),
                cliente=(order.get("contato", {}) or {}).get("nome") or order.get("nomeCliente") or "—",
                email=_extract_customer_email(detail, order),
                situacao=situacao_text,
                total_order=total_order_final,
                total_matched=order_total_matched,
                has_frete=_has_frete(detail, order),
                matched_items=matched_items,
            )

        filtered_orders = list(filtered_order_map.values())
        _inject_production_data(db, event_id, filtered_orders)
        _inject_event_tags(db, event_id, filtered_orders)

        logger.info(
            "event_sales_filter_done event_id=%s matched_orders=%s matched_items=%s total_matched=%.2f list_api_calls=1 detail_cache_hits=%s detail_api_fetched=%s detail_api_failed=%s local_fallback_used=%s total_api_calls=%s",
            str(event_id),
            len(filtered_orders),
            matched_items_count,
            total_matched,
            cache_hits,
            fetched,
            failed,
            local_fallback_used,
            1 + fetched,
        )

        return EventSalesResponse(
            event=event_response,
            summary=EventSalesSummaryResponse(
                orders_count=len(filtered_orders),
                matched_items_count=matched_items_count,
                total_matched=total_matched,
            ),
            orders=filtered_orders,
        )

    except BlingAuthError:
        raise HTTPException(status_code=401, detail="Sessão do Bling expirada. Reconecte sua conta.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar pedidos da campanha: {exc}")


@router.get("/{event_id}/tags")
async def list_event_order_tags(event_id: UUID, db: Session = Depends(get_db)):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    try:
        rows = OrderTagRepository.list_tags(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            scope_key="event",
            event_id=event_id,
        )
    except Exception as exc:
        logger.warning("event_list_tags_failed event_id=%s error=%s", str(event_id), str(exc))
        rows = []
    return {
        "tags": [
            {
                "id": str(row.id),
                "name": row.name,
            }
            for row in rows
        ]
    }


@router.put("/{event_id}/orders/{order_id}/tag")
async def set_event_order_tag(event_id: UUID, order_id: int, payload: OrderTagAssignRequest, db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError as _IntegrityError

    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    def _do_add_tag():
        return OrderTagRepository.add_tag_by_name(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            scope_key="event",
            event_id=event_id,
            bling_order_id=order_id,
            tag_name=payload.tag_name,
        )

    try:
        tags = _do_add_tag()
    except OrderTagSchemaError as exc:
        db.rollback()
        logger.error(
            "event_set_order_tag_schema_error event_id=%s order_id=%s error=%s",
            str(event_id), str(order_id), str(exc), exc_info=True,
        )
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except _IntegrityError:
        # Race condition: concurrent save of the same tag. Rollback and retry once.
        db.rollback()
        try:
            tags = _do_add_tag()
        except Exception as exc2:
            db.rollback()
            err_type = type(exc2).__name__
            logger.error(
                "event_set_order_tag_retry_failed event_id=%s order_id=%s error_type=%s error=%s",
                str(event_id), str(order_id), err_type, str(exc2), exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Falha ao salvar tag [{err_type}]: {exc2}")
    except Exception as exc:
        db.rollback()
        err_type = type(exc).__name__
        logger.error(
            "event_set_order_tag_failed event_id=%s order_id=%s error_type=%s error=%s",
            str(event_id), str(order_id), err_type, str(exc), exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Falha ao salvar tag [{err_type}]: {exc}")

    db.commit()
    return {"ok": True, "event_id": str(event_id), "order_id": int(order_id), "tag": tags[0] if tags else None, "tags": tags}


@router.delete("/{event_id}/orders/{order_id}/tag")
async def clear_event_order_tag(
    event_id: UUID,
    order_id: int,
    tag_name: str | None = Query(default=None, description="Optional specific tag name to remove"),
    db: Session = Depends(get_db),
):
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    if (tag_name or "").strip():
        try:
            tags = OrderTagRepository.remove_tag_by_name(
                db=db,
                tenant_id=DEFAULT_TENANT_ID,
                scope_key="event",
                event_id=event_id,
                bling_order_id=order_id,
                tag_name=tag_name,
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                "event_clear_specific_order_tag_failed event_id=%s order_id=%s tag=%s error=%s",
                str(event_id),
                str(order_id),
                tag_name,
                str(exc),
            )
            raise HTTPException(status_code=500, detail="Falha ao remover tag")
    else:
        try:
            OrderTagRepository.clear_assignment(
                db=db,
                tenant_id=DEFAULT_TENANT_ID,
                scope_key="event",
                event_id=event_id,
                bling_order_id=order_id,
            )
            tags = []
        except Exception as exc:
            db.rollback()
            logger.warning(
                "event_clear_all_order_tags_failed event_id=%s order_id=%s error=%s",
                str(event_id),
                str(order_id),
                str(exc),
            )
            raise HTTPException(status_code=500, detail="Falha ao remover tag")
    db.commit()
    return {"ok": True, "event_id": str(event_id), "order_id": int(order_id), "tag": tags[0] if tags else None, "tags": tags}


@router.get("/{event_id}/sync/version")
async def get_event_sync_version(event_id: UUID, db: Session = Depends(get_db)):
    """Lightweight version token for event sales delta polling."""
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    scope_key = scope_event_sales(event_id)
    row = SyncScopeVersionRepository.get_scope_version(db, DEFAULT_TENANT_ID, scope_key)
    return {
        "ok": True,
        "scope": scope_key,
        "current_version": int(row.version) if row else 0,
        "last_updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


@router.get("/{event_id}/sync/updates")
async def get_event_sync_updates(
    event_id: UUID,
    since: str | None = None,
    db: Session = Depends(get_db),
):
    """Incremental updates for event sales page (notes/status only)."""
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    since_dt = _parse_since_cursor(since)
    scope_key = scope_event_sales(event_id)
    version_row = SyncScopeVersionRepository.get_scope_version(db, DEFAULT_TENANT_ID, scope_key)
    status_rows = OrderSnapshotRepository.list_status_updates_since(db, DEFAULT_TENANT_ID, since_dt)
    production_rows = ItemProductionNoteRepository.list_updated_since(
        db,
        DEFAULT_TENANT_ID,
        since_dt,
        event_id=event_id,
    )

    return {
        "ok": True,
        "scope": scope_key,
        "current_version": int(version_row.version) if version_row else 0,
        "last_updated_at": version_row.updated_at.isoformat() if version_row and version_row.updated_at else None,
        "server_time": datetime.utcnow().isoformat(),
        "order_status_updates": [
            {
                "order_id": int(row.bling_order_id),
                "situacao": row.status_name,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in status_rows
        ],
        "production_updates": [
            {
                "sku": row.sku,
                "bling_order_id": int(row.bling_order_id) if row.bling_order_id is not None else None,
                "production_status": row.production_status,
                "notes": row.notes,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in production_rows
        ],
    }


@router.put("/{event_id}/items/{sku}/production", response_model=ItemProductionNoteResponse)
async def update_item_production(
    event_id: UUID,
    sku: str,
    body: ItemProductionNoteUpdateRequest,
    db: Session = Depends(get_db),
):
    """Upsert production status and notes for an item in a campaign.

    When all matched items of an order reach 'Embalado', automatically
    updates the Bling order status to 'Pronto para Envio' or 'Pronto para Retirada'.
    """
    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    norm_sku = sku.strip().upper()
    row = ItemProductionNoteRepository.upsert(
        db,
        DEFAULT_TENANT_ID,
        event_id,
        norm_sku,
        body.production_status,
        body.notes,
        bling_order_id=body.bling_order_id,
        preserve_existing_notes=not _field_was_provided(body, "notes"),
    )

    # Auto-update Bling when all items of an order become "Embalado".
    if body.production_status == "Embalado":
        await _check_and_update_bling_orders(db, event, event_id)

    SyncScopeVersionRepository.bump_scope(db, DEFAULT_TENANT_ID, scope_event_sales(event_id))
    SyncScopeVersionRepository.bump_scope(db, DEFAULT_TENANT_ID, SCOPE_ORDERS_GLOBAL)
    db.commit()

    return ItemProductionNoteResponse(
        sku=row.sku, production_status=row.production_status, notes=row.notes,
        bling_order_id=row.bling_order_id,
    )


async def _check_and_update_bling_orders(db: Session, event, event_id: UUID):
    """For each order in the event, if ALL matched items are Embalado,
    update Bling status to Pronto para Envio / Pronto para Retirada."""
    from app.models.database import BlingOrderSnapshotModel

    client = _make_client(db)
    if not client:
        return

    # Load production notes and event products.
    notes = ItemProductionNoteRepository.get_all_for_event(db, DEFAULT_TENANT_ID, event_id)
    note_map: dict[tuple[str, int | None], str] = {}
    sku_fallback_map: dict[str, str] = {}
    for n in notes:
        sku_key = n.sku.strip().upper()
        note_map[(sku_key, n.bling_order_id)] = n.production_status
        if n.bling_order_id is None:
            sku_fallback_map[sku_key] = n.production_status

    event_response = _map_event_response(db, event)
    selected_skus_canonical = {
        _canonical_sku(p.sku) for p in event_response.products if _canonical_sku(p.sku)
    }
    selected_product_ids = {
        pid for pid in (_to_optional_int(p.bling_product_id) for p in event_response.products) if pid is not None
    }

    # Get Bling situation IDs.
    sit_ids = await get_bling_status_ids(client)
    pronto_envio_id = sit_ids.get("pronto_envio")
    pronto_retirada_id = sit_ids.get("pronto_retirada")
    can_update_bling = bool(pronto_envio_id or pronto_retirada_id)
    if not can_update_bling:
        logger.warning("bling_situacoes_not_found applying local status fallback only")

    # Scan orders in event period.
    start_dt = datetime.combine(event.start_date, time.min)
    end_dt = datetime.combine(event.end_date, time.max)
    snapshot_rows = OrderSnapshotRepository.list_for_period(db, DEFAULT_TENANT_ID, start_dt, end_dt)

    for row in snapshot_rows:
        # Skip already-atendido or already-pronto orders.
        if row.status_id in _ATENDIDO_IDS or row.status_id in _CANCELADO_IDS:
            continue

        detail_payload = row.raw_detail if isinstance(row.raw_detail, dict) else {}
        order_payload = row.raw_order if isinstance(row.raw_order, dict) else {}
        order_items = _extract_order_items(detail_payload) or _extract_order_items(order_payload)
        matched = _match_event_items(order_items, selected_skus_canonical, selected_product_ids)
        if not matched:
            continue

        # Check if ALL matched items are Embalado.
        def _item_embalado(item: dict[str, Any]) -> bool:
            sku_key = (item.get("sku", "")).strip().upper()
            if not sku_key:
                return False
            status = note_map.get((sku_key, row.bling_order_id))
            if status is None:
                status = sku_fallback_map.get(sku_key)
            return status == "Embalado"

        all_embalado = all(_item_embalado(item) for item in matched)
        if not all_embalado:
            continue

        # Determine envio vs retirada.
        frete = _has_frete(detail_payload, order_payload)
        target_name = "Pronto para envio" if frete else "Pronto para retirada"
        target_id = pronto_envio_id if frete else pronto_retirada_id
        if not target_id:
            target_id = pronto_retirada_id if frete else pronto_envio_id

        snapshot = db.query(BlingOrderSnapshotModel).filter(
            BlingOrderSnapshotModel.bling_order_id == row.bling_order_id,
            BlingOrderSnapshotModel.tenant_id == DEFAULT_TENANT_ID,
        ).first()

        if not can_update_bling or not target_id:
            if snapshot:
                snapshot.status_name = target_name
                db.commit()
            logger.info(
                "order_status_local_fallback order_id=%s status=%s",
                row.bling_order_id,
                target_name,
            )
            continue

        try:
            await client.patch(f"/pedidos/vendas/{row.bling_order_id}/situacoes/{target_id}", {})
            # Update local snapshot.
            if snapshot:
                snapshot.status_id = target_id
                snapshot.status_name = target_name
                db.commit()
            logger.info("bling_order_status_updated order_id=%s new_status_id=%s", row.bling_order_id, target_id)
        except Exception as exc:
            if snapshot:
                snapshot.status_name = target_name
                db.commit()
            logger.warning(
                "bling_order_status_update_failed order_id=%s error=%s local_status_applied=%s",
                row.bling_order_id,
                str(exc),
                target_name,
            )


@router.put("/{event_id}/orders/{order_id}/status")
async def update_order_status(
    event_id: UUID,
    order_id: int,
    body: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a Bling order status (e.g. mark as Atendido)."""
    from app.models.database import BlingOrderSnapshotModel

    event = SalesEventRepository.get_by_id(db, event_id, DEFAULT_TENANT_ID)
    if not event:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

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

    local_only = False
    try:
        await client.patch(f"/pedidos/vendas/{order_id}/situacoes/{target_id}", {})
    except BlingAPIError as exc:
        logger.warning(
            "update_order_status_bling_error order_id=%s target_id=%s error=%s fallback_local=true",
            order_id,
            target_id,
            str(exc),
        )
        local_only = True

    # Update local snapshot.
    snapshot = db.query(BlingOrderSnapshotModel).filter(
        BlingOrderSnapshotModel.bling_order_id == order_id,
        BlingOrderSnapshotModel.tenant_id == DEFAULT_TENANT_ID,
    ).first()
    if snapshot:
        snapshot.status_id = target_id
        snapshot.status_name = body.situacao

    SyncScopeVersionRepository.bump_scope(db, DEFAULT_TENANT_ID, scope_event_sales(event_id))
    SyncScopeVersionRepository.bump_scope(db, DEFAULT_TENANT_ID, SCOPE_ORDERS_GLOBAL)
    db.commit()

    return {"ok": True, "order_id": order_id, "new_status": body.situacao, "local_only": local_only}
