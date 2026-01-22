"""Router for model template configuration endpoints."""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.infra.bling_client import BlingClient
from app.models.schemas import ModelTemplateResponse, ModelTemplateCreateRequest
from app.repositories.model_template_repo import ModelTemplateRepository
from app.repositories.model_repo import ModelRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config/templates", tags=["config"])

# Default tenant (Sprint 2: single tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[ModelTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    model_code: str = None,
):
    """
    List model templates.

    - **model_code**: Optional filter by model code.
    """
    logger.info("list_templates", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "model_code": model_code,
    })
    
    if model_code:
        templates = ModelTemplateRepository.list_by_model(db, DEFAULT_TENANT_ID, model_code)
    else:
        templates = ModelTemplateRepository.list_all(db, DEFAULT_TENANT_ID)
    
    return templates


@router.post("", response_model=ModelTemplateResponse, status_code=201)
async def create_template(
    request: ModelTemplateCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new model template."""
    logger.info("create_template", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "model_code": request.model_code,
        "template_kind": request.template_kind,
        "bling_product_id": request.bling_product_id,
    })
    
    # Verify model exists
    model = ModelRepository.get_by_code(db, DEFAULT_TENANT_ID, request.model_code)
    if not model:
        logger.warning("model_not_found_for_template", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "model_code": request.model_code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MODEL_NOT_FOUND",
                "message": f"Model '{request.model_code}' not found",
            },
        )
    
    # Check if template already exists
    existing = ModelTemplateRepository.get_by_model_and_kind(
        db, DEFAULT_TENANT_ID, request.model_code, request.template_kind
    )
    if existing:
        logger.warning("template_already_exists", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "model_code": request.model_code,
            "template_kind": request.template_kind,
        })
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEMPLATE_ALREADY_EXISTS",
                "message": f"Template already exists for {request.model_code}/{request.template_kind}",
            },
        )
    
    # Fetch product details from Bling
    bling_client = BlingClient()
    try:
        product = await bling_client.get_product(request.bling_product_id)
        bling_product_sku = product.get("codigo", "")
        bling_product_name = product.get("nome", "")
    except Exception as e:
        logger.error("bling_product_fetch_failed", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "bling_product_id": request.bling_product_id,
            "error": str(e),
        })
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BLING_PRODUCT_NOT_FOUND",
                "message": f"Bling product {request.bling_product_id} not found or error fetching",
                "details": str(e),
            },
        )
    
    # Create template
    template = ModelTemplateRepository.create(
        db,
        DEFAULT_TENANT_ID,
        request,
        bling_product_sku=bling_product_sku,
        bling_product_name=bling_product_name,
    )
    
    logger.info("template_created", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "template_id": str(template.id),
        "model_code": template.model_code,
        "template_kind": template.template_kind,
    })
    return template


@router.get("/{template_id}", response_model=ModelTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Get template by ID."""
    logger.info("get_template", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "template_id": template_id,
    })
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID format")
    
    template = ModelTemplateRepository.get_by_id(db, DEFAULT_TENANT_ID, template_uuid)
    if not template:
        logger.warning("template_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "template_id": template_id,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEMPLATE_NOT_FOUND",
                "message": f"Template {template_id} not found",
            },
        )
    return template


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Delete a template by ID."""
    logger.info("delete_template", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "template_id": template_id,
    })
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID format")
    
    success = ModelTemplateRepository.delete(db, DEFAULT_TENANT_ID, template_uuid)
    if not success:
        logger.warning("template_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "template_id": template_id,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEMPLATE_NOT_FOUND",
                "message": f"Template {template_id} not found",
            },
        )
    
    logger.info("template_deleted", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "template_id": template_id,
    })
