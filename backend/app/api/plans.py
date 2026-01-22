"""Plans API endpoints - Sprint 3."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from uuid import UUID

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
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


async def _check_bling_product(
    bling_client: Optional[BlingClient], sku: str
) -> Optional[Dict[str, Any]]:
    """Check if product exists in Bling by SKU and return enriched fields for diffing."""
    if not bling_client:
        return None

    try:
        response = await bling_client.get_produtos(params={"codigo": sku, "limite": 1})

        if not response or "data" not in response:
            return None

        data = response["data"]
        if not data:
            return None

        product = data[0]
        product_id = product.get("id")

        # Fetch full details for diffing
        detail = None
        if product_id:
            try:
                detail_resp = await bling_client.get_product(product_id)
                detail = detail_resp.get("data") if detail_resp else None
            except Exception as e:
                logger.warning(f"Error fetching full product for {sku}: {e}")

        enriched = detail or product

        return {
            "id": enriched.get("id", product_id),
            "codigo": enriched.get("codigo", sku),
            "nome": enriched.get("nome"),
            "formato": enriched.get("formato"),
            "situacao": enriched.get("situacao"),
            "preco": enriched.get("preco"),
            "precoVenda": enriched.get("precoVenda"),
            "descricaoCurta": enriched.get("descricaoCurta"),
            "descricaoComplementar": enriched.get("descricaoComplementar"),
            "categoria_id": enriched.get("categoria_id") or enriched.get("categoriaId"),
        }

    except Exception as e:
        logger.warning(f"Error checking Bling product {sku}: {e}")
        return None


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

        # Create checker function
        async def bling_checker(sku: str) -> Optional[Dict[str, Any]]:
            return await _check_bling_product(bling_client, sku)

        # Build plan
        builder = PlanBuilderNew(
            models_data=models_data,
            colors_data=colors_data,
            templates_data=templates_data,
            bling_checker=bling_checker,
            bling_client=bling_client,
        )

        plan = await builder.build_plan(request)

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
