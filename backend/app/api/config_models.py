"""Router for model configuration endpoints."""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.models.schemas import ModelResponse, ModelCreateRequest, ModelUpdateRequest, ErrorResponse
from app.repositories.model_repo import ModelRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config/models", tags=["config"])

# Default tenant (Sprint 2: single tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[ModelResponse])
def list_models(
    db: Session = Depends(get_db),
    all: bool = Query(False, description="Include inactive models"),
):
    """
    List models.

    - **all**: If true, include inactive models. Default: false (active only).
    """
    logger.info("list_models", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "all": all,
    })
    
    if all:
        models = ModelRepository.list_all(db, DEFAULT_TENANT_ID)
    else:
        models = ModelRepository.list_active(db, DEFAULT_TENANT_ID)
    
    return models


@router.post("", response_model=ModelResponse, status_code=201)
def create_model(
    request: ModelCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new model."""
    logger.info("create_model", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": request.code,
    })
    
    # Check if model already exists
    existing = ModelRepository.get_by_code(db, DEFAULT_TENANT_ID, request.code)
    if existing:
        # If model exists but is inactive, reactivate and update fields (keep same name)
        if getattr(existing, "is_active", True) is False:
            logger.info("model_reactivate", extra={
                "tenant_id": str(DEFAULT_TENANT_ID),
                "code": request.code,
            })
            existing.is_active = True
            # Keep same name as requested: same name as existing (do not override)
            # Update other fields from request
            if request.allowed_sizes is not None:
                existing.allowed_sizes = request.allowed_sizes
                existing.size_order = request.size_order or request.allowed_sizes
            elif request.size_order is not None:
                existing.size_order = request.size_order

            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        # Active duplicate → conflict
        logger.warning("model_already_exists", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": request.code,
        })
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MODEL_ALREADY_EXISTS",
                "message": f"Model '{request.code}' already exists",
            },
        )
    
    model = ModelRepository.create(db, DEFAULT_TENANT_ID, request)
    logger.info("model_created", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "model_id": str(model.id),
        "code": model.code,
    })
    return model


@router.get("/{code}", response_model=ModelResponse)
def get_model(
    code: str,
    db: Session = Depends(get_db),
):
    """Get model by code."""
    logger.info("get_model", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    model = ModelRepository.get_by_code(db, DEFAULT_TENANT_ID, code)
    if not model:
        logger.warning("model_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MODEL_NOT_FOUND",
                "message": f"Model '{code}' not found",
            },
        )
    return model


@router.put("/{code}", response_model=ModelResponse)
def update_model(
    code: str,
    request: ModelUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a model by code."""
    logger.info("update_model", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    model = ModelRepository.update(db, DEFAULT_TENANT_ID, code, request)
    if not model:
        logger.warning("model_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MODEL_NOT_FOUND",
                "message": f"Model '{code}' not found",
            },
        )
    
    logger.info("model_updated", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    return model


@router.delete("/{code}", status_code=204)
def delete_model(
    code: str,
    db: Session = Depends(get_db),
):
    """Delete (deactivate) a model by code."""
    logger.info("delete_model", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    success = ModelRepository.delete(db, DEFAULT_TENANT_ID, code)
    if not success:
        logger.warning("model_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MODEL_NOT_FOUND",
                "message": f"Model '{code}' not found",
            },
        )
    
    logger.info("model_deleted", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
