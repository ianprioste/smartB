"""Plans API endpoints - Sprint 3."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from uuid import UUID

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
from app.settings import settings
from app.models.schemas import (
    PlanNewRequest,
    PlanResponse,
    PlanSaveRequest,
    PlanSavedResponse,
    ErrorResponse,
)
from app.models.enums import PlanTypeEnum
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.model_repo import ModelRepository
from app.repositories.color_repo import ColorRepository
from app.repositories.model_template_repo import ModelTemplateRepository
from app.repositories.plan_repo import PlanRepository
from app.domain.plan_builder_new import PlanBuilderNew, PlanBuilderError
from app.infra.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/plans", tags=["Plans"])

# TODO: Replace with real tenant resolution
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


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
    bling_client: Optional[BlingClient], skus: list[str]
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
        params.append(("tipo", "T"))
        params.append(("limite", str(min(len(skus) + 10, 100))))
        
        logger.info(f"Bulk checking {len(skus)} SKUs in Bling: {skus[:5]}..." if len(skus) > 5 else f"Bulk checking SKUs: {skus}")
        
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

        # Fallback for rare false negatives from bulk endpoint.
        # Use ONE extra bulk retry (chunked) instead of per-SKU calls.
        missing_skus = [sku for sku, product in result.items() if product is None]
        if missing_skus:
            chunk_size = 100
            for i in range(0, len(missing_skus), chunk_size):
                chunk = missing_skus[i:i + chunk_size]
                try:
                    retry_params = [("codigos[]", sku) for sku in chunk]
                    retry_params.append(("tipo", "T"))
                    retry_params.append(("limite", str(min(len(chunk) + 10, 100))))

                    fallback_resp = await bling_client.client.get(
                        "/produtos",
                        params=retry_params,
                        headers=bling_client._get_headers(),
                    )
                    if fallback_resp.status_code != 200:
                        logger.warning(
                            f"Fallback bulk returned status {fallback_resp.status_code} for {len(chunk)} SKU(s)"
                        )
                        continue

                    fallback_data = fallback_resp.json() if fallback_resp.content else {}
                    fallback_items = (fallback_data or {}).get("data") or []

                    for fallback_item in fallback_items:
                        fallback_code = str((fallback_item or {}).get("codigo", "")).strip().upper()
                        requested_key = requested_key_by_norm.get(fallback_code)
                        if not requested_key:
                            continue
                        product_id = fallback_item.get("id")
                        result[requested_key] = {
                            "id": fallback_item.get("id", product_id),
                            "codigo": fallback_item.get("codigo", requested_key),
                            "nome": fallback_item.get("nome"),
                            "formato": fallback_item.get("formato"),
                            "situacao": fallback_item.get("situacao"),
                            "preco": fallback_item.get("preco"),
                            "precoVenda": fallback_item.get("precoVenda"),
                            "descricaoCurta": fallback_item.get("descricaoCurta"),
                            "descricaoComplementar": fallback_item.get("descricaoComplementar"),
                            "categoria_id": fallback_item.get("categoria_id") or fallback_item.get("categoriaId"),
                        }
                        logger.info(f"Fallback bulk found SKU {requested_key} (id={product_id})")
                except Exception as fallback_error:
                    logger.warning(f"Fallback bulk lookup failed for chunk of {len(chunk)} SKU(s): {fallback_error}")
        
        logger.info(f"Bulk check complete: Found {len([v for v in result.values() if v])} of {len(skus)} products")
        logger.info(f"DEBUG: Result dict populated with {len([v for v in result.values() if v is not None])} products")
        return result
        
    except Exception as e:
        logger.error(f"Error checking Bling products bulk: {e}", exc_info=True)
        return result


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
            except Exception as e:
                print(f"DEBUG: Erro no bulk check: {e}")
                logger.warning(f"Error during bulk Bling check, continuing with empty cache: {e}")
                bling_products_cache = {sku: None for sku in required_skus}

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

        # Create plan in database
        saved_plan = plan_repo.create(
            tenant_id=TENANT_ID,
            plan_type=PlanTypeEnum.NEW_PRINT,
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
