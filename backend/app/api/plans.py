"""Plans API endpoints - Sprint 3."""
import asyncio
import uuid as _uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from uuid import UUID

from app.infra.db import get_db, SessionLocal
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
from app.settings import settings
from app.models.schemas import (
    PlanNewRequest,
    PlanPlainRequest,
    PlanResponse,
    PlanItem,
    PlanItemTemplate,
    PlanSummary,
    PlanOverrides,
    PlanSaveRequest,
    PlanSavedResponse,
    ErrorResponse,
)
from app.models.enums import PlanTypeEnum, PlanItemActionEnum, TemplateKindEnum
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.model_repo import ModelRepository
from app.repositories.color_repo import ColorRepository
from app.repositories.model_template_repo import ModelTemplateRepository
from app.repositories.plan_repo import PlanRepository
from app.domain.plan_builder_new import PlanBuilderNew, PlanBuilderError
from app.domain.template_merge import TemplateMerge
from app.infra.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/plans", tags=["Plans"])

_direct_plan_tasks: dict[str, dict[str, Any]] = {}

# TODO: Replace with real tenant resolution
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _calculate_diff_summary_plain(
    existing_product: Dict[str, Any],
    computed_payload: Dict[str, Any],
    *,
    category_override_active: bool,
) -> list[str]:
    """Compare existing product with computed payload and return changed fields."""
    if not existing_product:
        return ["*"]

    diff_fields: list[str] = []
    fields_to_compare = [
        ("preco", "preco"),
        ("nome", "nome"),
        ("precoVenda", "precoVenda"),
        ("descricaoCurta", "descricaoCurta"),
        ("descricaoComplementar", "descricaoComplementar"),
        ("ncm", "ncm"),
        ("cest", "cest"),
    ]

    for existing_field, computed_field in fields_to_compare:
        expected = computed_payload.get(computed_field)
        actual = existing_product.get(existing_field)
        if expected is None:
            continue
        if actual != expected:
            diff_fields.append(existing_field)

    # Compare structured variation label when that data is available in the
    # existing payload (edit-by-id flow). Bulk listing may not include it.
    expected_variacao_nome = ((computed_payload.get("variacao") or {}).get("nome") or "").strip()
    if expected_variacao_nome and "variacao" in existing_product:
        actual_variacao = existing_product.get("variacao") or {}
        actual_variacao_nome = ""
        if isinstance(actual_variacao, dict):
            actual_variacao_nome = str(actual_variacao.get("nome") or "").strip()
        elif isinstance(actual_variacao, str):
            actual_variacao_nome = actual_variacao.strip()
        if actual_variacao_nome != expected_variacao_nome:
            diff_fields.append("variacao.nome")

    if category_override_active:
        expected_cat = computed_payload.get("categoria_id")
        actual_cat = existing_product.get("categoria_id")
        if expected_cat is not None and actual_cat != expected_cat:
            diff_fields.append("categoria_id")

    return diff_fields


@router.post(
    "/new-plain",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def create_new_plain_plan(
    request: PlanPlainRequest,
    db: Session = Depends(get_db),
):
    """Create plain product plan (parent + variations) with parent SKU/name defined by user."""
    logger.info(f"Creating plain plan for parent_sku={request.parent_sku}")

    try:
        model_repo = ModelRepository
        color_repo = ColorRepository
        template_repo = ModelTemplateRepository

        models = model_repo.list_all(db, TENANT_ID)
        models_data = {
            m.code: {
                "name": m.name,
                "allowed_sizes": m.allowed_sizes,
                "size_order": m.size_order,
            }
            for m in models
        }

        colors = color_repo.list_all(db, TENANT_ID)
        colors_data = {c.code: c.name for c in colors}

        templates = template_repo.list_all(db, TENANT_ID)
        templates_data: Dict[str, Dict[str, int]] = {}
        for template in templates:
            if template.model_code not in templates_data:
                templates_data[template.model_code] = {}
            templates_data[template.model_code][template.template_kind.value] = template.bling_product_id

        model_code = request.model_code
        if model_code not in models_data:
            raise PlanBuilderError(f"Model {model_code} not found in configuration")

        for color_code in request.colors:
            if color_code not in colors_data:
                raise PlanBuilderError(f"Color {color_code} not found in configuration")

        sizes = request.sizes or models_data[model_code].get("allowed_sizes", [])
        if not sizes:
            raise PlanBuilderError(f"No sizes available for model {model_code}")

        parent_sku = request.parent_sku.strip().upper()
        parent_name = request.parent_name.strip()

        if not parent_sku:
            raise PlanBuilderError("parent_sku is required")
        if not parent_name:
            raise PlanBuilderError("parent_name is required")

        required_skus = {parent_sku}
        child_skus: list[tuple[str, str, str]] = []
        for color_code in request.colors:
            for size in sizes:
                child_sku = f"{parent_sku}{color_code}{size}".upper()
                child_skus.append((child_sku, color_code, size))
                required_skus.add(child_sku)

        bling_client = await _get_bling_client(db)
        bling_products_cache: Dict[str, Optional[Dict[str, Any]]] = {sku: None for sku in required_skus}
        if bling_client:
            bling_products_cache = await _check_bling_products_bulk(bling_client, list(required_skus))

        if request.edit_parent_id and bling_client:
            try:
                existing_resp = await bling_client.get(f"/produtos/{request.edit_parent_id}")
                existing_data = (existing_resp or {}).get("data", {})
                if existing_data:
                    bling_products_cache[parent_sku] = existing_data
                    # Populate child variation cache from the parent's variacoes array so
                    # the plan correctly detects existing children as UPDATE/NOOP instead of CREATE.
                    for variation in (existing_data.get("variacoes") or []):
                        var_sku = str(variation.get("codigo") or "").strip().upper()
                        if var_sku and var_sku in bling_products_cache:
                            bling_products_cache[var_sku] = {
                                "id": variation.get("id"),
                                "codigo": variation.get("codigo"),
                                "nome": variation.get("nome"),
                                "variacao": variation.get("variacao"),
                                "formato": variation.get("formato"),
                                "situacao": variation.get("situacao"),
                                "preco": variation.get("preco"),
                                "precoVenda": variation.get("precoVenda"),
                                "descricaoCurta": variation.get("descricaoCurta"),
                                "descricaoComplementar": variation.get("descricaoComplementar"),
                                "categoria_id": variation.get("categoria_id") or variation.get("categoriaId"),
                            }
                    logger.info(
                        f"Populated cache from edit_parent_id={request.edit_parent_id}: "
                        f"parent + {len(existing_data.get('variacoes') or [])} variation(s)"
                    )
            except Exception as e:
                logger.warning(f"Could not fetch edit_parent_id {request.edit_parent_id}: {e}")

        model_name = models_data[model_code].get("name", model_code)

        model_templates = templates_data.get(model_code, {})
        parent_template_kind = (
            TemplateKindEnum.BASE_PARENT.value
            if TemplateKindEnum.BASE_PARENT.value in model_templates
            else TemplateKindEnum.BASE_PLAIN.value
        )
        parent_template_id = model_templates.get(parent_template_kind)
        child_template_id = model_templates.get(TemplateKindEnum.BASE_PLAIN.value)

        parent_template_payload: Dict[str, Any] = {}
        child_template_payload: Dict[str, Any] = {}
        if bling_client and parent_template_id:
            try:
                parent_template_payload = ((await bling_client.get_product(parent_template_id)) or {}).get("data") or {}
            except Exception as e:
                logger.warning(f"Failed to fetch parent template payload for {model_code}: {e}")
        if bling_client and child_template_id:
            try:
                child_template_payload = ((await bling_client.get_product(child_template_id)) or {}).get("data") or {}
            except Exception as e:
                logger.warning(f"Failed to fetch child template payload for {model_code}: {e}")

        category_override_active = request.overrides.category_override_id is not None

        items: list[PlanItem] = []

        parent_payload = TemplateMerge.merge(
            parent_template_payload,
            sku=parent_sku,
            name=parent_name,
            overrides=request.overrides,
            price=request.price,
            model_name=model_name,
            print_name="Produto Liso",
        )
        parent_existing = bling_products_cache.get(parent_sku)

        if parent_existing is None:
            if not parent_template_payload:
                parent_action = PlanItemActionEnum.BLOCKED
                parent_reason = "MISSING_TEMPLATE_PAYLOAD"
                parent_diff = []
                parent_message = "Template do pai liso sem payload - não é possível executar CREATE"
            else:
                parent_action = PlanItemActionEnum.CREATE
                parent_reason = None
                parent_diff = []
                parent_message = "Parent plain product will be created"
        else:
            parent_diff = _calculate_diff_summary_plain(
                parent_existing,
                parent_payload,
                category_override_active=category_override_active,
            )
            if parent_diff:
                parent_action = PlanItemActionEnum.UPDATE
                parent_reason = None
                parent_message = "Product exists but needs update"
            else:
                parent_action = PlanItemActionEnum.NOOP
                parent_reason = None
                parent_message = "Product already up to date"

        items.append(
            PlanItem(
                sku=parent_sku,
                entity="BASE_PARENT",
                action=parent_action,
                hard_dependencies=[],
                soft_dependencies=[],
                template=PlanItemTemplate(model=model_code, kind=parent_template_kind, fallback_used=(parent_template_kind == TemplateKindEnum.BASE_PLAIN.value)),
                status=parent_action,
                reason=parent_reason,
                message=parent_message,
                warnings=[],
                diff_summary=parent_diff,
                existing_product=parent_existing,
                template_ref={
                    "model_code": model_code,
                    "template_kind": parent_template_kind,
                    "bling_product_id": parent_template_id,
                    "bling_product_sku": parent_template_payload.get("codigo") if parent_template_payload else None,
                },
                overrides_used={
                    "price": request.price,
                    "short_description": parent_payload.get("descricaoCurta"),
                    "complement_description": parent_payload.get("descricaoComplementar"),
                    "category_override_id": request.overrides.category_override_id,
                    "complement_same_as_short": request.overrides.complement_same_as_short,
                },
                computed_payload_preview=parent_payload,
            )
        )

        for child_sku, color_code, size in child_skus:
            color_name = colors_data.get(color_code, color_code)
            child_name = f"{parent_name} Cor: {color_name};Tamanho: {size}"
            child_payload = TemplateMerge.merge(
                child_template_payload,
                sku=child_sku,
                name=child_name,
                overrides=request.overrides,
                price=request.price,
                model_name=model_name,
                print_name="Produto Liso",
            )
            # Plain variations must carry a stable variation descriptor, otherwise
            # Bling may render option labels as undefined/malformed.
            child_payload["variacao"] = {
                "nome": f"Cor: {color_name};Tamanho: {size}",
                "ordem": 0,
            }
            child_existing = bling_products_cache.get(child_sku)

            if child_existing is None:
                if not child_template_payload:
                    child_action = PlanItemActionEnum.BLOCKED
                    child_reason = "MISSING_TEMPLATE_PAYLOAD"
                    child_diff = []
                    child_message = "Template da variação lisa sem payload - não é possível executar CREATE"
                else:
                    child_action = PlanItemActionEnum.CREATE
                    child_reason = None
                    child_diff = []
                    child_message = "Child plain variation will be created"
            else:
                child_diff = _calculate_diff_summary_plain(
                    child_existing,
                    child_payload,
                    category_override_active=category_override_active,
                )
                if child_diff:
                    child_action = PlanItemActionEnum.UPDATE
                    child_reason = None
                    child_message = "Product exists but needs update"
                else:
                    child_action = PlanItemActionEnum.NOOP
                    child_reason = None
                    child_message = "Product already up to date"

            items.append(
                PlanItem(
                    sku=child_sku,
                    entity="BASE_VARIATION",
                    action=child_action,
                    hard_dependencies=[parent_sku],
                    soft_dependencies=[],
                    template=PlanItemTemplate(model=model_code, kind=TemplateKindEnum.BASE_PLAIN.value, fallback_used=False),
                    status=child_action,
                    reason=child_reason,
                    message=child_message,
                    warnings=[],
                    diff_summary=child_diff,
                    existing_product=child_existing,
                    template_ref={
                        "model_code": model_code,
                        "template_kind": TemplateKindEnum.BASE_PLAIN.value,
                        "bling_product_id": child_template_id,
                        "bling_product_sku": child_template_payload.get("codigo") if child_template_payload else None,
                    },
                    overrides_used={
                        "price": request.price,
                        "short_description": child_payload.get("descricaoCurta"),
                        "complement_description": child_payload.get("descricaoComplementar"),
                        "category_override_id": request.overrides.category_override_id,
                        "complement_same_as_short": request.overrides.complement_same_as_short,
                    },
                    computed_payload_preview=child_payload,
                )
            )

        summary = PlanSummary(
            models=1,
            colors=len(request.colors),
            total_skus=len(items),
            create_count=sum(1 for i in items if i.action == PlanItemActionEnum.CREATE),
            update_count=sum(1 for i in items if i.action == PlanItemActionEnum.UPDATE),
            noop_count=sum(1 for i in items if i.action == PlanItemActionEnum.NOOP),
            blocked_count=sum(1 for i in items if i.action == PlanItemActionEnum.BLOCKED),
        )

        return PlanResponse(
            planVersion="1.0",
            type="NEW_PLAIN",
            summary=summary,
            items=items,
            has_blockers=summary.blocked_count > 0,
            options=request.options,
        )

    except PlanBuilderError as e:
        logger.error(f"Plain plan builder error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PLAN_BUILDER_ERROR",
                "message": str(e),
            },
        )
    except BlingRefreshTokenExpiredError as e:
        logger.error(f"Bling token expired during plain plan generation: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "code": "BLING_TOKEN_EXPIRED",
                "message": "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token.",
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error creating plain plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Erro inesperado: {str(e)}",
            },
        )


async def _get_bling_client(db: Session) -> Optional[BlingClient]:
    """Get authenticated Bling client."""
    token = BlingTokenRepository.get_by_tenant(db, TENANT_ID)

    if not token:
        return None

    async def on_token_refresh(access_token: str, refresh_token: str, expires_at):
        """Update token in database."""
        BlingTokenRepository.create_or_update(
            db, TENANT_ID, access_token, refresh_token, expires_at
        )

    return BlingClient(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_expires_at=token.expires_at,
        on_token_refresh=on_token_refresh,
    )


async def _check_bling_products_bulk(
    bling_client: Optional[BlingClient], skus: list[str], include_type_filter: bool = True
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Check if products exist in Bling by SKUs (bulk operation).
    
    Makes a single API call with multiple SKUs and returns a dictionary
    mapping SKU -> product data for caching.
    
    Args:
        bling_client: Bling client instance
        skus: List of SKUs to check
        
    Returns:
        Dictionary mapping SKU -> product data (or None if not found)
    """
    result: Dict[str, Optional[Dict[str, Any]]] = {sku: None for sku in skus}
    requested_key_by_norm = {
        (sku or "").strip().upper(): sku for sku in skus
    }
    
    if not bling_client or not skus:
        return result
    
    try:
        # Make single API call with all SKUs
        # Build params as list of tuples to properly handle multiple codigos[] params
        # This creates URL like: /produtos?codigos[]=SKU1&codigos[]=SKU2&limite=100
        params = [("codigos[]", sku) for sku in skus]
        # Include product variations in lookup (critical for size/color SKUs).
        if include_type_filter:
            params.append(("tipo", "T"))
        params.append(("limite", str(min(len(skus) + 10, 100))))
        
        # Log all requested SKUs for debugging (especially parent/base SKUs)
        # Extract simple SKUs that are likely parents or bases (no numbers = usually base, short = usually parent)
        simple_skus = [s for s in skus if len(s) <= 10 and str(s).isupper()]
        base_skus = [s for s in simple_skus if not any(c.isdigit() for c in s)]
        logger.info(f"Bulk checking {len(skus)} SKUs (including {len(base_skus)} potential bases/parents): {skus[:5]}...")
        if base_skus:
            logger.debug(f"Base/Parent SKUs in request: {base_skus}")
        
        # Use raw httpx client to send the request properly
        response = await bling_client.client.get(
            f"/produtos",
            params=params,
            headers=bling_client._get_headers()
        )
        
        logger.info(f"Bling API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"Bling API returned status {response.status_code}")
            return result
        
        data = response.json()
        logger.info(f"DEBUG: Bling response data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        
        if not data or "data" not in data:
            logger.warning(f"No 'data' field in Bling response for {len(skus)} SKUs")
            logger.info(f"DEBUG: Full response: {data}")
            return result
        
        products = data.get("data", [])
        logger.info(f"Found {len(products)} products in Bling response for {len(skus)} requested SKUs")
        logger.info(f"DEBUG: Products from Bling: {[p.get('codigo') for p in products[:10]]}...")
        
        # Process each product
        for product in products:
            sku = product.get("codigo")
            if not sku:
                logger.warning(f"Product from Bling has no 'codigo' field: {product.get('id')}")
                continue

            requested_key = requested_key_by_norm.get(str(sku).strip().upper())
            if not requested_key:
                logger.warning(f"Product SKU {sku} not in requested list, skipping")
                continue
                
            product_id = product.get("id")
            logger.info(f"Processing found product: {sku} (id={product_id})")
            
            # Log if this is a base SKU
            if requested_key in base_skus:
                logger.info(f"✓ Found BASE SKU {requested_key} in Bling (id={product_id})")
            
            # Keep bulk check lightweight: list payload is enough for plan decisions.
            enriched = product
            
            result[requested_key] = {
                "id": enriched.get("id", product_id),
                "codigo": enriched.get("codigo", requested_key),
                "nome": enriched.get("nome"),
                "formato": enriched.get("formato"),
                "situacao": enriched.get("situacao"),
                "preco": enriched.get("preco"),
                "precoVenda": enriched.get("precoVenda"),
                "descricaoCurta": enriched.get("descricaoCurta"),
                "descricaoComplementar": enriched.get("descricaoComplementar"),
                "categoria_id": enriched.get("categoria_id") or enriched.get("categoriaId"),
            }

            # Bling's list endpoint does NOT return child variations (formato=E) as top-level
            # entries — they are embedded inside the parent's variacoes array.
            # Populate the cache for any requested child SKUs found here so the plan
            # correctly identifies them as existing (NOOP/UPDATE) instead of CREATE.
            for variation in (product.get("variacoes") or []):
                var_sku_raw = str(variation.get("codigo") or "").strip()
                var_sku_norm = var_sku_raw.upper()
                var_requested_key = requested_key_by_norm.get(var_sku_norm)
                if var_requested_key and result.get(var_requested_key) is None:
                    result[var_requested_key] = {
                        "id": variation.get("id"),
                        "codigo": variation.get("codigo"),
                        "nome": variation.get("nome"),
                        "formato": variation.get("formato"),
                        "situacao": variation.get("situacao"),
                        "preco": variation.get("preco"),
                        "precoVenda": variation.get("precoVenda"),
                        "descricaoCurta": variation.get("descricaoCurta"),
                        "descricaoComplementar": variation.get("descricaoComplementar"),
                        "categoria_id": variation.get("categoria_id") or variation.get("categoriaId"),
                    }
                    logger.info(f"✓ Found VARIATION SKU {var_requested_key} inside parent {requested_key} variacoes")

        logger.info(f"Bulk check complete: Found {len([v for v in result.values() if v])} of {len(skus)} products")
        logger.info(f"DEBUG: Result dict populated with {len([v for v in result.values() if v is not None])} products")
        return result
        
    except Exception as e:
        logger.error(f"Error checking Bling products bulk: {e}", exc_info=True)
        return result


async def _run_direct_new_plan(task_id: str, request_payload: Dict[str, Any]) -> None:
    """Background coroutine: build a new print plan without blocking the HTTP request."""
    _direct_plan_tasks[task_id] = {"state": "PROGRESS", "message": "Gerando plano..."}
    db = SessionLocal()
    try:
        request = PlanNewRequest(**request_payload)
        plan = await create_new_plan(request, db)
        _direct_plan_tasks[task_id] = {
            "state": "SUCCESS",
            "plan": plan.model_dump(),
        }
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        _direct_plan_tasks[task_id] = {
            "state": "FAILURE",
            "status_code": exc.status_code,
            "error": detail,
        }
    except Exception as exc:
        logger.error("direct_plan_generation_failed task_id=%s error=%s", task_id, str(exc), exc_info=True)
        _direct_plan_tasks[task_id] = {
            "state": "FAILURE",
            "status_code": 500,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to create plan",
                "details": str(exc),
            },
        }
    finally:
        db.close()


@router.post("/new/async")
async def create_new_plan_async(
    request: PlanNewRequest,
    db: Session = Depends(get_db),
):
    """Start new plan generation in background and return a polling id immediately."""
    token = BlingTokenRepository.get_by_tenant(db, TENANT_ID)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "BLING_TOKEN_EXPIRED",
                "message": "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token.",
            },
        )

    task_id = f"direct-{_uuid_mod.uuid4().hex}"
    _direct_plan_tasks[task_id] = {"state": "PENDING", "message": "Plano enfileirado."}
    asyncio.create_task(_run_direct_new_plan(task_id, request.model_dump()))
    return {"task_id": task_id, "state": "PENDING"}


@router.get("/new/status/{task_id}")
async def get_new_plan_status(task_id: str):
    """Get status for a background new plan generation task."""
    payload = _direct_plan_tasks.get(task_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")

    state = payload.get("state")
    if state == "SUCCESS":
        return {
            "status": "completed",
            "task_id": task_id,
            "state": state,
            "plan": payload.get("plan"),
        }

    if state == "FAILURE":
        return {
            "status": "failed",
            "task_id": task_id,
            "state": state,
            "error": payload.get("error"),
            "status_code": payload.get("status_code", 500),
        }

    return {
        "status": "running" if state == "PROGRESS" else "queued",
        "task_id": task_id,
        "state": state,
        "message": payload.get("message"),
    }


@router.post(
    "/new",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def create_new_plan(
    request: PlanNewRequest,
    db: Session = Depends(get_db),
):
    """
    Create new print plan (dry-run).
    
    Generates a complete plan with preview but does NOT execute anything.
    Does NOT create any products in Bling.
    
    Returns plan with CREATE/UPDATE/NOOP/BLOCKED status for each SKU.
    
    IMPORTANT - Execution Semantics:
    ===============================
    - Items with action=CREATE/UPDATE: Ready to execute in Sprint 4
    - Items with action=BLOCKED: Executor MUST skip these (not executable)
    - Items with action=NOOP: Executor can skip (already correct)
    - Items with reason=MISSING_TEMPLATE_PAYLOAD: BLOCKED (no payload data to create)
    
    Preview vs Execution:
    - Preview: Shows all items safely (safe fallback for missing template_payload: {})
    - Execution: Only items with action in {CREATE, UPDATE} are processed
    - BLOCKED items remain for user review but are NOT executed by the worker
    """
    print(f"\n{'='*80}")
    print(f"CHAMOU /api/plans/new")
    print(f"Models: {[m.code for m in request.models]}, Colors: {request.colors}")
    print(f"{'='*80}\n")
    
    logger.info(f"Creating plan for print {request.print.code}")

    try:
        # Load configuration data
        model_repo = ModelRepository
        color_repo = ColorRepository
        template_repo = ModelTemplateRepository

        # Get all models
        models = model_repo.list_all(db, TENANT_ID)
        models_data = {
            m.code: {
                "name": m.name,
                "allowed_sizes": m.allowed_sizes,
                "size_order": m.size_order,
            }
            for m in models
        }

        # Get all colors
        colors = color_repo.list_all(db, TENANT_ID)
        colors_data = {c.code: c.name for c in colors}

        # Get all templates grouped by model
        templates = template_repo.list_all(db, TENANT_ID)
        templates_data: Dict[str, Dict[str, int]] = {}
        for template in templates:
            if template.model_code not in templates_data:
                templates_data[template.model_code] = {}
            templates_data[template.model_code][template.template_kind.value] = template.bling_product_id

        # Get Bling client for checking existing products
        bling_client = await _get_bling_client(db)

        # Create temporary builder to collect all required SKUs
        async def bling_checker(sku: str) -> Optional[Dict[str, Any]]:
            # This will be overridden by the cache, so it shouldn't be called much
            return None

        temp_builder = PlanBuilderNew(
            models_data=models_data,
            colors_data=colors_data,
            templates_data=templates_data,
            bling_checker=bling_checker,
            bling_client=bling_client,
        )
        
        # Collect all SKUs that will be needed
        required_skus = list(temp_builder.collect_all_required_skus(request))
        print(f"DEBUG: Collected {len(required_skus)} required SKUs")
        print(f"DEBUG: Required SKUs sample: {required_skus[:10]}")
        
        # Log base/parent SKUs specifically (these should be simple like "CAMINF")
        base_parent_skus = [s for s in required_skus if len(s) <= 10 and str(s).isupper()]
        print(f"DEBUG: Potential BASE_PARENT SKUs: {base_parent_skus}")
        
        logger.info(f"Bulk checking {len(required_skus)} SKUs in Bling")
        
        # Make single bulk API call to Bling for all SKUs
        bling_products_cache = {}
        if required_skus and bling_client:
            try:
                print(f"\nDEBUG: Iniciando bulk check de {len(required_skus)} SKUs")
                bling_products_cache = await _check_bling_products_bulk(bling_client, required_skus)
                found_count = sum(1 for v in bling_products_cache.values() if v is not None)
                print(f"DEBUG: Bulk check completo: {found_count} de {len(required_skus)} encontrados")
                
                # Log which SKUs were found
                found_skus = [sku for sku, prod in bling_products_cache.items() if prod is not None]
                if found_skus:
                    print(f"DEBUG: SKUs encontrados ({len(found_skus)}): {found_skus[:5]}")
                    
                not_found_skus = [sku for sku, prod in bling_products_cache.items() if prod is None]
                if not_found_skus:
                    print(f"DEBUG: SKUs NÃO encontrados ({len(not_found_skus)}): {not_found_skus[:5]}")
                
                logger.info(f"Bulk check complete: found {found_count}/{len(required_skus)} products in Bling")
                
                # Log specifically whether base_parent SKUs were found
                base_parent_results = {sku: prod is not None for sku in base_parent_skus if sku in bling_products_cache}
                if base_parent_results:
                    found_bases = [sku for sku, found in base_parent_results.items() if found]
                    not_found_bases = [sku for sku, found in base_parent_results.items() if not found]
                    if found_bases:
                        print(f"DEBUG: BASE_PARENT SKUs encontrados: {found_bases}")
                        logger.info(f"Found BASE_PARENT SKUs: {found_bases}")
                    if not_found_bases:
                        print(f"DEBUG: BASE_PARENT SKUs NÃO encontrados: {not_found_bases}")
                        logger.warning(f"Base parent SKUs not found in Bling: {not_found_bases}")
            except Exception as e:
                print(f"DEBUG: Erro no bulk check: {e}")
                logger.warning(f"Error during bulk Bling check, continuing with empty cache: {e}")
                bling_products_cache = {sku: None for sku in required_skus}

        # Fallback: some base plain variations may not be returned when the
        # product type filter is applied in list queries. Retry only missing
        # BASE_VARIATION SKUs without that filter.
        if bling_client and request.models:
            from app.domain.sku_engine import SkuEngine as _SkuEngine
            _sku_engine = _SkuEngine()
            missing_base_variations: list[str] = []
            for model_req in request.models:
                sizes = model_req.sizes or models_data.get(model_req.code, {}).get("allowed_sizes", [])
                for color_code in request.colors:
                    for size in sizes:
                        base_var_sku = _sku_engine.base_plain(model_req.code, color_code, size)
                        if base_var_sku in bling_products_cache and bling_products_cache.get(base_var_sku) is None:
                            missing_base_variations.append(base_var_sku)
            if missing_base_variations:
                try:
                    fallback_checked = await _check_bling_products_bulk(
                        bling_client,
                        missing_base_variations,
                        include_type_filter=False,
                    )
                    recovered = 0
                    for sku, product in fallback_checked.items():
                        if product is not None and bling_products_cache.get(sku) is None:
                            bling_products_cache[sku] = product
                            recovered += 1
                    if recovered:
                        logger.info(
                            f"Recovered {recovered}/{len(missing_base_variations)} missing BASE_VARIATION SKUs "
                            f"using fallback bulk check without type filter"
                        )
                except Exception as e:
                    logger.warning(f"Fallback bulk check for BASE_VARIATION SKUs failed: {e}")

        # Bling's list endpoint does NOT include child variations (formato=E) in its
        # response — they are only available via GET /produtos/{id} (detail endpoint).
        # For each BASE_PARENT found in the bulk check, fetch its full detail and
        # populate the cache with its variacoes so the plan correctly identifies
        # existing base variations as NOOP/UPDATE instead of CREATE.
        if bling_client:
            base_parent_fetch_tasks = []
            base_parent_skus_to_enrich = []
            for model_req in request.models:
                bp_sku = model_req.code.upper()
                bp_data = bling_products_cache.get(bp_sku)
                if bp_data and bp_data.get("id"):
                    base_parent_fetch_tasks.append(bling_client.get_product(int(bp_data["id"])))
                    base_parent_skus_to_enrich.append(bp_sku)
            if base_parent_fetch_tasks:
                try:
                    detail_results = await asyncio.gather(*base_parent_fetch_tasks, return_exceptions=True)
                    for bp_sku, detail_resp in zip(base_parent_skus_to_enrich, detail_results):
                        if isinstance(detail_resp, Exception):
                            logger.warning(f"Could not fetch detail for BASE_PARENT {bp_sku}: {detail_resp}")
                            continue
                        parent_detail = (detail_resp or {}).get("data", {})
                        for variation in (parent_detail.get("variacoes") or []):
                            var_sku = str(variation.get("codigo") or "").strip().upper()
                            if var_sku and var_sku in bling_products_cache:
                                bling_products_cache[var_sku] = {
                                    "id": variation.get("id"),
                                    "codigo": variation.get("codigo"),
                                    "nome": variation.get("nome"),
                                    "formato": variation.get("formato"),
                                    "situacao": variation.get("situacao"),
                                    "preco": variation.get("preco"),
                                    "precoVenda": variation.get("precoVenda"),
                                    "descricaoCurta": variation.get("descricaoCurta"),
                                    "descricaoComplementar": variation.get("descricaoComplementar"),
                                    "categoria_id": variation.get("categoria_id") or variation.get("categoriaId"),
                                }
                                logger.info(f"✓ Populated BASE_VARIATION {var_sku} from BASE_PARENT {bp_sku} detail")
                        logger.info(
                            f"Enriched BASE_PARENT {bp_sku}: "
                            f"{len(parent_detail.get('variacoes') or [])} variation(s) fetched"
                        )
                except Exception as e:
                    logger.warning(f"Error enriching base parent variations: {e}")

        # If editing an existing product by ID, fetch it and inject into cache
        # under the new parent SKU so the plan builder sees it as UPDATE (not CREATE)
        if request.edit_parent_id and bling_client and request.models:
            try:
                from app.domain.sku_engine import SkuEngine as _SkuEngine
                _sku_engine = _SkuEngine()
                existing_resp = await bling_client.get(f"/produtos/{request.edit_parent_id}")
                existing_data = (existing_resp or {}).get("data", {})
                if existing_data:
                    # Inject for the first model (edit mode targets one parent product)
                    first_model_code = request.models[0].code
                    new_parent_sku = _sku_engine.parent_printed(first_model_code, request.print.code)
                    bling_products_cache[new_parent_sku] = existing_data
                    logger.info(f"edit_parent_id={request.edit_parent_id}: injected into cache as {new_parent_sku}")
            except Exception as e:
                logger.warning(f"Could not fetch edit_parent_id {request.edit_parent_id}: {e}")

        # Create final builder with pre-loaded cache
        async def bling_checker_cached(sku: str) -> Optional[Dict[str, Any]]:
            # Use pre-loaded cache, avoid individual calls
            return bling_products_cache.get(sku)

        builder = PlanBuilderNew(
            models_data=models_data,
            colors_data=colors_data,
            templates_data=templates_data,
            bling_checker=bling_checker_cached,
            bling_client=bling_client,
            bling_cache=bling_products_cache,  # Pass pre-loaded cache
        )

        plan = await builder.build_plan(request)

        # Debug: print all items with status
        print("\n=== PLAN DEBUG: All items with status ===")
        for item in plan.items:
            print(f"  {item.sku}: action={item.action}, status={item.status}")
        print("=========================================\n")

        logger.info(
            f"Plan created successfully: {plan.summary.total_skus} SKUs, "
            f"has_blockers={plan.has_blockers}"
        )

        return plan

    except PlanBuilderError as e:
        logger.error(f"Plan builder error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PLAN_BUILDER_ERROR",
                "message": str(e),
            },
        )

    except BlingRefreshTokenExpiredError as e:
        logger.error(f"Bling token expired during plan generation: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "code": "BLING_TOKEN_EXPIRED",
                "message": "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token.",
            },
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error creating plan: {e}", exc_info=True)
        
        # Check for token-related errors in the exception message
        if "Refresh token expired" in error_msg or "401" in error_msg:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "BLING_TOKEN_EXPIRED",
                    "message": "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token.",
                },
            )
        
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to create plan",
                "details": str(e),
            },
        )


@router.post(
    "/new/save",
    response_model=PlanSavedResponse,
    responses={
        400: {"model": ErrorResponse},
    },
)
async def save_plan(
    request: PlanSaveRequest,
    db: Session = Depends(get_db),
):
    """
    Save a plan to database.
    
    Plan will be saved with DRAFT status.
    This allows later execution or review.
    """
    logger.info(f"Saving plan type={request.plan.type}")

    try:
        plan_repo = PlanRepository(db)

        # Convert plan to dict for storage
        plan_dict = request.plan.model_dump()
        try:
            plan_type = PlanTypeEnum(request.plan.type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_PLAN_TYPE",
                    "message": f"Unsupported plan type: {request.plan.type}",
                },
            )

        # Create plan in database
        saved_plan = plan_repo.create(
            tenant_id=TENANT_ID,
            plan_type=plan_type,
            input_payload=plan_dict,  # In real scenario, store original request
            plan_payload=plan_dict,
        )

        logger.info(f"Plan saved with id={saved_plan.id}")

        return PlanSavedResponse(
            id=saved_plan.id,
            type=saved_plan.type.value,
            status=saved_plan.status.value,
            created_at=saved_plan.created_at,
        )

    except Exception as e:
        logger.error(f"Error saving plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to save plan",
                "details": str(e),
            },
        )
