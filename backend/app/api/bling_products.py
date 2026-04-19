"""Router for Bling product search endpoints."""
import asyncio
import logging
import time
from typing import Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.infra.bling_client import BlingClient
from app.models.schemas import BlingProductSearchResponse, BlingProductDetailResponse, BlingProductSearchItem
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.product_snapshot_repo import ProductSnapshotRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bling/products", tags=["bling"])

# Fixed tenant ID for Sprint 1 (single-tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
CATALOG_CACHE_TTL_SECONDS = 180
_catalog_cache: dict[str, tuple[float, list[BlingProductSearchItem]]] = {}


def invalidate_catalog_cache() -> None:
    """Clear in-memory catalog cache after product/stock webhook updates."""
    _catalog_cache.clear()


def _unwrap_bling_product(product: dict[str, Any]) -> dict[str, Any]:
    """Normalize Bling payloads that may come wrapped in a top-level data object."""
    if isinstance(product, dict) and isinstance(product.get("data"), dict):
        return product["data"]
    return product


def _extract_parent_id(product: dict[str, Any]) -> Optional[int]:
    """Extract parent product id from the different shapes returned by Bling."""
    variacao = product.get("variacao") or {}
    produto_pai = variacao.get("produtoPai") or {}

    return (
        produto_pai.get("id")
        or product.get("idProdutoPai")
        or product.get("pai")
    )


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_stock_quantity(product: dict[str, Any]) -> Optional[float]:
    """Extract stock quantity from known Bling response shapes."""
    estoque = product.get("estoque") if isinstance(product.get("estoque"), dict) else None
    saldo_estoque = product.get("saldoEstoque") if isinstance(product.get("saldoEstoque"), dict) else None

    candidates = [
        product.get("quantidade"),
        product.get("estoqueAtual"),
        product.get("saldo"),
        product.get("saldoVirtualTotal"),
        product.get("saldoFisicoTotal"),
        estoque.get("quantidade") if estoque else None,
        estoque.get("saldoVirtualTotal") if estoque else None,
        estoque.get("saldoFisicoTotal") if estoque else None,
        saldo_estoque.get("saldoVirtualTotal") if saldo_estoque else None,
        saldo_estoque.get("saldoFisicoTotal") if saldo_estoque else None,
    ]

    for candidate in candidates:
        qty = _to_float(candidate)
        if qty is not None:
            return qty
    return None


async def _fill_missing_stock_quantities(
    bling_client: BlingClient,
    items: list[BlingProductSearchItem],
) -> list[BlingProductSearchItem]:
    """Fill stock quantity for paged items using detail endpoint when list payload is incomplete."""
    missing = [item for item in items if item.quantidade_estoque is None]
    if not missing:
        return items

    detail_tasks = [bling_client.get_product(item.id) for item in missing]
    detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

    stock_by_id: dict[int, Optional[float]] = {}
    for item, detail_result in zip(missing, detail_results):
        if isinstance(detail_result, Exception):
            logger.warning(
                "bling_stock_detail_failed",
                extra={"product_id": item.id, "error": str(detail_result)},
            )
            continue

        detail_data = _unwrap_bling_product(detail_result)
        stock_by_id[item.id] = _extract_stock_quantity(detail_data)

    return [
        item.model_copy(update={"quantidade_estoque": stock_by_id.get(item.id, item.quantidade_estoque)})
        for item in items
    ]


def _build_search_item(product: dict[str, Any]) -> BlingProductSearchItem:
    """Build a search/list item from either list or detail payloads."""
    product_data = _unwrap_bling_product(product)

    return BlingProductSearchItem(
        id=product_data.get("id"),
        codigo=product_data.get("codigo", ""),
        nome=product_data.get("nome", ""),
        product_kind=product_data.get("product_kind"),
        formato=product_data.get("formato"),
        situacao=product_data.get("situacao"),
        tipo_estoque=(product_data.get("estrutura") or {}).get("tipoEstoque"),
        pai=_extract_parent_id(product_data),
        quantidade_estoque=_extract_stock_quantity(product_data),
    )


def _build_catalog_params(page: int, limit: int, q: Optional[str]) -> dict[str, Any]:
    """Build standard Bling product list params."""
    params = {
        "pagina": page,
        "limite": limit,
        "criterio": 1,
    }

    if q:
        # Treat short, space-free queries as SKU codes (case-insensitive)
        if len(q) <= 20 and " " not in q:
            params["codigos[]"] = [q.upper()]
        else:
            params["nome"] = q

    return params


def _get_catalog_cache_key(q: Optional[str], include_hierarchy: bool) -> str:
    query_key = (q or "").strip() or "__all__"
    mode_key = "hierarchy" if include_hierarchy else "flat"
    return f"{query_key}::{mode_key}"


def _read_cached_catalog(q: Optional[str], include_hierarchy: bool) -> Optional[list[BlingProductSearchItem]]:
    cache_key = _get_catalog_cache_key(q, include_hierarchy)
    cached_entry = _catalog_cache.get(cache_key)
    if not cached_entry:
        return None

    cached_at, cached_items = cached_entry
    if time.monotonic() - cached_at > CATALOG_CACHE_TTL_SECONDS:
        _catalog_cache.pop(cache_key, None)
        return None

    return cached_items


def _write_cached_catalog(q: Optional[str], include_hierarchy: bool, items: list[BlingProductSearchItem]) -> None:
    _catalog_cache[_get_catalog_cache_key(q, include_hierarchy)] = (time.monotonic(), items)


def _sort_catalog_items(items: list[BlingProductSearchItem]) -> list[BlingProductSearchItem]:
    return sorted(
        items,
        key=lambda item: (
            item.pai or item.id,
            1 if item.pai else 0,
            (item.nome or "").lower(),
        ),
    )


def _build_snapshot_item(row) -> BlingProductSearchItem:
    return BlingProductSearchItem(
        id=int(row.bling_product_id),
        codigo=row.codigo or "",
        nome=row.nome or f"Produto {row.bling_product_id}",
        product_kind=row.product_kind.value if row.product_kind is not None else None,
        formato=row.formato,
        situacao=row.situacao,
        tipo_estoque=None,
        pai=int(row.parent_product_id) if row.parent_product_id is not None else None,
        quantidade_estoque=row.stock_quantity,
    )


def _list_from_snapshot(db: Session, q: Optional[str], page: int, limit: int) -> BlingProductSearchResponse:
    try:
        rows = ProductSnapshotRepository.list_by_query(db, DEFAULT_TENANT_ID, q or "")
        items = _sort_catalog_items([_build_snapshot_item(row) for row in rows])
        paged_items, total_groups = _paginate_grouped_items(items, page, limit)
        return BlingProductSearchResponse(
            total=total_groups,
            page=page,
            limit=limit,
            items=paged_items,
            total_items=len(items),
        )
    except Exception as exc:
        logger.warning("list_from_snapshot_failed", extra={"error": str(exc)})
        return BlingProductSearchResponse(
            total=0,
            page=page,
            limit=limit,
            items=[],
            total_items=0,
        )


def _search_from_snapshot(
    db: Session,
    q: str,
    page: int,
    limit: int,
    include_children: bool,
) -> BlingProductSearchResponse:
    """Fast local search for campaign product picker using persisted snapshot."""
    rows = ProductSnapshotRepository.list_by_query(db, DEFAULT_TENANT_ID, q or "")
    items = _sort_catalog_items([_build_snapshot_item(row) for row in rows])

    if not include_children:
        items = [item for item in items if not item.pai]

    start = (page - 1) * limit
    end = start + limit
    return BlingProductSearchResponse(
        total=len(items),
        page=page,
        limit=limit,
        items=items[start:end],
        total_items=len(items),
    )


def _can_use_raw_hierarchy(items: list[BlingProductSearchItem]) -> bool:
    """Return True when list payload already has enough parent-child links.

    We only need heavy detail enrichment when many non-parent products still lack
    `pai` relation. For full catalog loads this heuristic avoids a large N+1.
    """
    non_parent_items = [item for item in items if item.formato != "V"]
    if not non_parent_items:
        return True

    linked_count = sum(1 for item in non_parent_items if item.pai)
    coverage = linked_count / len(non_parent_items)
    return coverage >= 0.9


async def _fetch_all_products(
    bling_client: BlingClient,
    q: Optional[str],
    batch_size: int = 100,
) -> list[dict[str, Any]]:
    """Fetch the complete product catalog from Bling across all pages."""
    all_products: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    current_page = 1

    while True:
        results = await bling_client.get_produtos(
            params=_build_catalog_params(page=current_page, limit=batch_size, q=q)
        )
        data = results.get("data", []) if isinstance(results, dict) else []

        if not data:
            break

        for product in data:
            product_id = product.get("id")
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            all_products.append(product)

        if len(data) < batch_size:
            break

        current_page += 1

    return all_products


async def _enrich_catalog_with_hierarchy(
    bling_client: BlingClient,
    products: list[dict[str, Any]],
    *,
    resolve_missing_parents: bool,
) -> list[BlingProductSearchItem]:
    """Enrich the full catalog with parent-child relationships from Bling details."""
    items = [_build_search_item(product) for product in products]
    if not items:
        return items

    item_ids = {item.id for item in items}
    parent_candidates = [item for item in items if item.formato == "V"]
    parent_detail_tasks = [bling_client.get_product(item.id) for item in parent_candidates]
    parent_detail_results = await asyncio.gather(*parent_detail_tasks, return_exceptions=True)

    child_to_parent: dict[int, int] = {}
    detailed_parents: dict[int, BlingProductSearchItem] = {}
    detailed_children: dict[int, BlingProductSearchItem] = {}

    for parent_item, detail_result in zip(parent_candidates, parent_detail_results):
        if isinstance(detail_result, Exception):
            logger.warning(
                "bling_parent_detail_enrich_failed",
                extra={"product_id": parent_item.id, "error": str(detail_result)},
            )
            detailed_parents[parent_item.id] = parent_item
            continue

        detail_data = _unwrap_bling_product(detail_result)
        detailed_parent = _build_search_item(detail_data)
        detailed_parents[detailed_parent.id] = detailed_parent

        for variation in detail_data.get("variacoes", []):
            variation_id = variation.get("id")
            if variation_id:
                child_to_parent[variation_id] = detailed_parent.id
                variation_item = _build_search_item(variation)
                detailed_children[variation_id] = variation_item.model_copy(update={"pai": detailed_parent.id})

    missing_parent_ids: set[int] = set()
    if resolve_missing_parents:
        unresolved_items = [item for item in items if item.id not in child_to_parent and item.formato != "V"]
        unresolved_tasks = [bling_client.get_product(item.id) for item in unresolved_items]
        unresolved_results = await asyncio.gather(*unresolved_tasks, return_exceptions=True)

        for item, detail_result in zip(unresolved_items, unresolved_results):
            if isinstance(detail_result, Exception):
                logger.warning(
                    "bling_filtered_product_detail_failed",
                    extra={"product_id": item.id, "error": str(detail_result)},
                )
                continue

            detail_item = _build_search_item(detail_result)
            if detail_item.pai:
                child_to_parent[item.id] = detail_item.pai
                if detail_item.pai not in item_ids:
                    missing_parent_ids.add(detail_item.pai)

    extra_parent_items: list[BlingProductSearchItem] = []
    if missing_parent_ids:
        missing_parent_tasks = [bling_client.get_product(parent_id) for parent_id in sorted(missing_parent_ids)]
        missing_parent_results = await asyncio.gather(*missing_parent_tasks, return_exceptions=True)

        for parent_id, detail_result in zip(sorted(missing_parent_ids), missing_parent_results):
            if isinstance(detail_result, Exception):
                logger.warning(
                    "bling_missing_parent_detail_failed",
                    extra={"product_id": parent_id, "error": str(detail_result)},
                )
                continue

            parent_item = _build_search_item(detail_result)
            detailed_parents[parent_item.id] = parent_item
            extra_parent_items.append(parent_item)

    enriched_items: list[BlingProductSearchItem] = []
    for item in items:
        if item.id in detailed_parents:
            item = detailed_parents[item.id]
        elif item.id in detailed_children:
            item = detailed_children[item.id]
        parent_id = child_to_parent.get(item.id, item.pai)
        enriched_items.append(item.model_copy(update={"pai": parent_id}))

    combined_items = extra_parent_items + enriched_items
    deduped_items: dict[int, BlingProductSearchItem] = {item.id: item for item in combined_items}

    return _sort_catalog_items(list(deduped_items.values()))


async def _fetch_parent_with_all_variations(
    bling_client: BlingClient,
    product_item: BlingProductSearchItem,
) -> list[BlingProductSearchItem]:
    """
    Fetch a parent product with all its variations.
    If the product is a variation, fetches the parent.
    If the product is a parent, fetches all variations.
    """
    # Determine which ID to use for fetching details
    parent_id = product_item.pai if product_item.pai else product_item.id
    
    try:
        parent_detail = await bling_client.get_product(parent_id)
        parent_data = _unwrap_bling_product(parent_detail)
        parent_item = _build_search_item(parent_data)
        
        # Extract all variations
        variations = parent_data.get("variacoes", [])
        variation_items = [_build_search_item(var) for var in variations]
        
        # Combine: parent first, then variations sorted by name
        all_items = [parent_item] + sorted(
            variation_items,
            key=lambda item: (item.nome or "").lower()
        )
        
        return all_items
    except Exception as e:
        logger.warning(
            "fetch_parent_with_variations_failed",
            extra={"product_id": product_item.id, "parent_id": parent_id, "error": str(e)},
        )
        return [product_item]


def _paginate_grouped_items(
    items: list[BlingProductSearchItem],
    page: int,
    limit: int,
) -> tuple[list[BlingProductSearchItem], int]:
    """Paginate by parent group while keeping all child rows with their parent."""
    grouped_items: dict[int, list[BlingProductSearchItem]] = {}
    group_order: list[int] = []

    for item in items:
        group_id = item.pai or item.id
        if group_id not in grouped_items:
            grouped_items[group_id] = []
            group_order.append(group_id)
        grouped_items[group_id].append(item)

    total_groups = len(group_order)
    start = (page - 1) * limit
    end = start + limit
    selected_group_ids = group_order[start:end]

    paged_items: list[BlingProductSearchItem] = []
    for group_id in selected_group_ids:
        paged_items.extend(grouped_items[group_id])

    return paged_items, total_groups


def _filter_items_by_partial_query(items: list[BlingProductSearchItem], query: str) -> list[BlingProductSearchItem]:
    """Filter products by partial match on SKU or product name."""
    q = (query or "").strip().casefold()
    if not q:
        return items

    scored: list[tuple[int, BlingProductSearchItem]] = []
    for item in items:
        sku = (item.codigo or "").casefold()
        name = (item.nome or "").casefold()

        if q not in sku and q not in name:
            continue

        # Basic ranking: SKU startswith > SKU contains > NAME startswith > NAME contains
        if sku.startswith(q):
            score = 0
        elif q in sku:
            score = 1
        elif name.startswith(q):
            score = 2
        else:
            score = 3

        scored.append((score, item))

    scored.sort(key=lambda tup: (tup[0], (tup[1].codigo or "").lower(), (tup[1].nome or "").lower()))
    return [item for _, item in scored]


async def _enrich_products_with_hierarchy(
    bling_client: BlingClient,
    products: list[dict[str, Any]],
) -> list[BlingProductSearchItem]:
    """Enrich paginated list items with parent ids and missing parent products."""
    items = [_build_search_item(product) for product in products]
    if not items:
        return items

    page_ids = {item.id for item in items}
    detail_tasks = [bling_client.get_product(item.id) for item in items]
    detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

    missing_parent_ids: set[int] = set()
    enriched_items: list[BlingProductSearchItem] = []
    all_variation_items: list[BlingProductSearchItem] = []

    for item, detail_result in zip(items, detail_results):
        if isinstance(detail_result, Exception):
            logger.warning(
                "bling_product_detail_enrich_failed",
                extra={"product_id": item.id, "error": str(detail_result)},
            )
            enriched_items.append(item)
            continue

        enriched_item = _build_search_item(detail_result)
        enriched_items.append(enriched_item)

        # If this is a parent product (formato="V"), extract all variations
        detail_data = _unwrap_bling_product(detail_result)
        if detail_data.get("formato") == "V":
            variations = detail_data.get("variacoes", [])
            for variation in variations:
                variation_item = _build_search_item(variation)
                all_variation_items.append(variation_item)

        if enriched_item.pai and enriched_item.pai not in page_ids:
            missing_parent_ids.add(enriched_item.pai)

    extra_parent_items: list[BlingProductSearchItem] = []
    if missing_parent_ids:
        parent_tasks = [bling_client.get_product(parent_id) for parent_id in sorted(missing_parent_ids)]
        parent_results = await asyncio.gather(*parent_tasks, return_exceptions=True)

        for parent_id, parent_result in zip(sorted(missing_parent_ids), parent_results):
            if isinstance(parent_result, Exception):
                logger.warning(
                    "bling_parent_product_fetch_failed",
                    extra={"product_id": parent_id, "error": str(parent_result)},
                )
                continue

            extra_parent_items.append(_build_search_item(parent_result))

    combined_items = extra_parent_items + enriched_items + all_variation_items
    deduped: dict[int, BlingProductSearchItem] = {item.id: item for item in combined_items}
    
    return _sort_catalog_items(list(deduped.values()))


@router.get("/search", response_model=BlingProductSearchResponse)
async def search_products(
    q: str = Query(..., min_length=1, description="Search query (name or SKU)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    include_children: bool = Query(True, description="When false, hide child variations and return only parent items."),
    search_by: Optional[str] = Query(None, description="Search by 'name' or 'sku'. Auto-detect if not specified."),
    db: Session = Depends(get_db),
):
    """
    Search products in Bling.

    - **q**: Search query (product name or SKU/codigo).
    - **page**: Page number (1-indexed).
    - **limit**: Items per page (1-100).
    - **search_by**: Force search by 'name' or 'sku'. If not specified, auto-detects based on query format.
    
    **Auto-detection:** Queries that are short, uppercase, and have no spaces are treated as SKU.
    """
    logger.info("search_products", extra={
        "query": q,
        "page": page,
        "limit": limit,
        "include_children": include_children,
        "search_by": search_by,
    })

    # Prefer local snapshot for predictable low-latency campaign search.
    try:
        snapshot_response = _search_from_snapshot(db, q, page, limit, include_children)
        if snapshot_response.total_items and snapshot_response.total_items > 0:
            logger.info(
                "search_products_snapshot_hit",
                extra={"query": q, "total_items": snapshot_response.total_items},
            )
            return snapshot_response
    except Exception as exc:
        logger.warning("search_products_snapshot_failed", extra={"query": q, "error": str(exc)})
    
    # Get Bling OAuth2 token from database
    bling_token = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not bling_token:
        # Fallback mode: keep products page usable from local snapshot cache.
        snapshot_response = _list_from_snapshot(db, q, page, limit)
        if snapshot_response.total_items and snapshot_response.total_items > 0:
            return snapshot_response
        raise HTTPException(
            status_code=401,
            detail="Nenhum token OAuth2 encontrado. Por favor, autentique-se primeiro em /auth/callback."
        )
    
    # Callback to save refreshed token back to database
    def save_refreshed_token(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info("token_refreshed_and_saved", extra={"tenant_id": str(DEFAULT_TENANT_ID)})
    
    # Initialize Bling client with token and callback
    bling_client = BlingClient(
        access_token=bling_token.access_token,
        refresh_token=bling_token.refresh_token,
        token_expires_at=bling_token.expires_at,
        on_token_refresh=save_refreshed_token,
    )
    
    try:
        # Partial search (SKU/name) is done over cached full catalog for predictable behavior.
        all_items = _read_cached_catalog(None, False)
        if all_items is None:
            raw_products = await _fetch_all_products(bling_client, None)
            all_items = _sort_catalog_items([_build_search_item(product) for product in raw_products])
            _write_cached_catalog(None, False, all_items)

        matched = _filter_items_by_partial_query(all_items, q)

        if not include_children:
            parents_by_id = {item.id: item for item in all_items if not item.pai}
            parent_only: list[BlingProductSearchItem] = []
            seen_parent_ids: set[int] = set()

            for item in matched:
                parent_id = item.pai or item.id
                parent_item = parents_by_id.get(parent_id)
                if not parent_item or parent_item.id in seen_parent_ids:
                    continue

                seen_parent_ids.add(parent_item.id)
                parent_only.append(parent_item)

            matched = _sort_catalog_items(parent_only)

        # Paginate flat list for search endpoint
        start = (page - 1) * limit
        end = start + limit
        paged_items = matched[start:end]

        return BlingProductSearchResponse(
            total=len(matched),
            page=page,
            limit=limit,
            items=paged_items,
        )
    
    except Exception as e:
        error_msg = str(e)
        logger.error("bling_search_failed", extra={
            "query": q,
            "error": error_msg,
            "error_type": type(e).__name__,
        })
        
        # Import here to avoid circular dependency
        from app.infra.bling_client import BlingRefreshTokenExpiredError
        
        # Parse error to provide better message
        if isinstance(e, BlingRefreshTokenExpiredError) or "Refresh token expired" in error_msg:
            detail_msg = "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token."
            status_code = 401
            code = "BLING_TOKEN_EXPIRED"
        elif "404" in error_msg or "Not Found" in error_msg:
            detail_msg = "Nenhum produto encontrado no Bling com este nome ou SKU. Verifique se o produto existe no Bling."
            status_code = 404
            code = "BLING_PRODUCT_NOT_FOUND"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            detail_msg = "Erro de autenticação com Bling. Token pode estar inválido. Tente autenticar novamente em /auth/bling/connect."
            status_code = 401
            code = "BLING_UNAUTHORIZED"
        elif "429" in error_msg:
            detail_msg = "Limite de requisições excedido. Tente novamente em alguns minutos."
            status_code = 429
            code = "BLING_RATE_LIMITED"
        else:
            detail_msg = f"Erro ao buscar produtos no Bling: {error_msg}"
            status_code = 500
            code = "BLING_SEARCH_FAILED"
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": code,
                "message": detail_msg,
                "details": error_msg,
                "needs_reauth": isinstance(e, BlingRefreshTokenExpiredError) or "Refresh token expired" in error_msg,
            },
        )


@router.get("/list/all", response_model=BlingProductSearchResponse)
async def list_all_products(
    q: Optional[str] = Query(None, description="Optional filter by name or SKU"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    include_hierarchy: bool = Query(True, description="Include parent/child hierarchy enrichment (heavier)."),
    db: Session = Depends(get_db),
):
    """
    List all products from Bling with optional filtering.

    - **q**: Optional search query (product name or SKU). If empty, returns all products.
    - **page**: Page number (1-indexed), paginated by produto principal/grupo.
    - **limit**: Groups per page (1-100).
    """
    logger.info("list_all_products", extra={
        "query": q,
        "page": page,
        "limit": limit,
        "include_hierarchy": include_hierarchy,
    })
    
    # Get Bling OAuth2 token from database
    bling_token = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not bling_token:
        # No Bling token: serve from local snapshot when available.
        snapshot_response = _list_from_snapshot(db, q, page, limit)
        if snapshot_response.total_items and snapshot_response.total_items > 0:
            logger.info("list_all_products_no_token_snapshot_fallback", extra={"total_items": snapshot_response.total_items})
            return snapshot_response
        raise HTTPException(
            status_code=401,
            detail="Nenhum token OAuth2 encontrado. Por favor, autentique-se primeiro em /auth/callback."
        )
    
    # Callback to save refreshed token back to database
    def save_refreshed_token(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info("token_refreshed_and_saved", extra={"tenant_id": str(DEFAULT_TENANT_ID)})
    
    # Initialize Bling client with token and callback
    bling_client = BlingClient(
        access_token=bling_token.access_token,
        refresh_token=bling_token.refresh_token,
        token_expires_at=bling_token.expires_at,
        on_token_refresh=save_refreshed_token,
    )
    
    try:
        enriched_items = _read_cached_catalog(q, include_hierarchy)
        if enriched_items is None:
            raw_products = await _fetch_all_products(bling_client, q)
            if include_hierarchy:
                raw_items = [_build_search_item(product) for product in raw_products]
                if _can_use_raw_hierarchy(raw_items):
                    logger.info(
                        "list_all_products_fast_hierarchy",
                        extra={"query": q, "items": len(raw_items)},
                    )
                    enriched_items = _sort_catalog_items(raw_items)
                else:
                    logger.info(
                        "list_all_products_full_hierarchy",
                        extra={"query": q, "items": len(raw_items)},
                    )
                    enriched_items = await _enrich_catalog_with_hierarchy(
                        bling_client,
                        raw_products,
                        resolve_missing_parents=bool(q),
                    )
            else:
                enriched_items = _sort_catalog_items([_build_search_item(product) for product in raw_products])
            _write_cached_catalog(q, include_hierarchy, enriched_items)

        # If filtering by SKU and found exactly one parent, fetch all its variations
        if include_hierarchy and q and len(enriched_items) == 1:
            first_item = enriched_items[0]
            if first_item.formato == "V":  # Is a parent
                complete_items = await _fetch_parent_with_all_variations(bling_client, first_item)
                enriched_items = complete_items
                # Invalidate cache for this query since we've augmented the results
                _catalog_cache.pop(_get_catalog_cache_key(q, include_hierarchy), None)

        paged_items, total_groups = _paginate_grouped_items(enriched_items, page, limit)
        paged_items = await _fill_missing_stock_quantities(bling_client, paged_items)
        
        return BlingProductSearchResponse(
            total=total_groups,
            page=page,
            limit=limit,
            items=paged_items,
            total_items=len(enriched_items),
        )
    
    except Exception as e:
        error_msg = str(e)
        logger.error("bling_list_products_failed", extra={
            "query": q,
            "error": error_msg,
            "error_type": type(e).__name__,
        })

        from app.infra.bling_client import BlingRefreshTokenExpiredError

        # Always try snapshot first regardless of error type.
        snapshot_response = _list_from_snapshot(db, q, page, limit)
        if snapshot_response.total_items and snapshot_response.total_items > 0:
            logger.info("bling_list_products_snapshot_fallback", extra={"query": q, "total_items": snapshot_response.total_items})
            return snapshot_response

        # Snapshot is empty — raise a meaningful error for auth failures.
        if isinstance(e, BlingRefreshTokenExpiredError) or "Refresh token expired" in error_msg:
            detail_msg = "Token do Bling expirado. É necessário autenticar novamente."
            status_code = 401
            code = "BLING_TOKEN_EXPIRED"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            detail_msg = "Erro de autenticação com Bling. Token pode estar inválido."
            status_code = 401
            code = "BLING_AUTH_ERROR"
        else:
            # Graceful degradation: return empty snapshot response.
            logger.warning("bling_list_products_returning_empty_fallback", extra={"query": q, "error": error_msg})
            return snapshot_response
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": code,
                "message": detail_msg,
                "details": error_msg,
            },
        )

@router.get("/{product_id}", response_model=BlingProductDetailResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a Bling product.

    - **product_id**: Bling product ID.
    """
    logger.info("get_product", extra={
        "product_id": product_id,
    })
    
    # Get Bling OAuth2 token from database
    bling_token = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not bling_token:
        raise HTTPException(
            status_code=401,
            detail="Nenhum token OAuth2 encontrado. Por favor, autentique-se primeiro em /auth/callback."
        )
    
    # Callback to save refreshed token back to database
    def save_refreshed_token(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info("token_refreshed_and_saved", extra={"tenant_id": str(DEFAULT_TENANT_ID)})
    
    # Initialize Bling client with token and callback
    bling_client = BlingClient(
        access_token=bling_token.access_token,
        refresh_token=bling_token.refresh_token,
        token_expires_at=bling_token.expires_at,
        on_token_refresh=save_refreshed_token,
    )
    
    try:
        product = _unwrap_bling_product(await bling_client.get_product(product_id))
        
        return BlingProductDetailResponse(
            id=product.get("id"),
            codigo=product.get("codigo", ""),
            nome=product.get("nome", ""),
            formato=product.get("formato"),
            situacao=product.get("situacao"),
            descricao=product.get("descricao"),
            descricao_curta=product.get("descricaoCurta"),
            descricao_complementar=product.get("descricaoComplementar"),
            preco=product.get("preco"),
            categoria_id=product.get("categoria", {}).get("id"),
        )
    
    except Exception as e:
        logger.error("bling_product_fetch_failed", extra={
            "product_id": product_id,
            "error": str(e),
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BLING_PRODUCT_NOT_FOUND",
                "message": f"Product {product_id} not found in Bling",
                "details": str(e),
            },
        )
