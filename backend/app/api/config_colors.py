"""Router for color configuration endpoints."""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.models.schemas import ColorResponse, ColorCreateRequest, ColorUpdateRequest
from app.repositories.color_repo import ColorRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config/colors", tags=["config"])

# Default tenant (Sprint 2: single tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[ColorResponse])
def list_colors(
    db: Session = Depends(get_db),
    all: bool = Query(False, description="Include inactive colors"),
):
    """
    List colors.

    - **all**: If true, include inactive colors. Default: false (active only).
    """
    logger.info("list_colors", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "all": all,
    })
    
    if all:
        colors = ColorRepository.list_all(db, DEFAULT_TENANT_ID)
    else:
        colors = ColorRepository.list_active(db, DEFAULT_TENANT_ID)
    
    return colors


@router.post("", response_model=ColorResponse, status_code=201)
def create_color(
    request: ColorCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new color."""
    logger.info("create_color", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": request.code,
    })
    
    # Check if color already exists
    existing = ColorRepository.get_by_code(db, DEFAULT_TENANT_ID, request.code)
    if existing:
        # If color exists but is inactive, reactivate (keep same name)
        if getattr(existing, "is_active", True) is False:
            logger.info("color_reactivate", extra={
                "tenant_id": str(DEFAULT_TENANT_ID),
                "code": request.code,
            })
            existing.is_active = True
            # Keep same name as existing; no other fields to update
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        # Active duplicate → conflict
        logger.warning("color_already_exists", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": request.code,
        })
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COLOR_ALREADY_EXISTS",
                "message": f"Color '{request.code}' already exists",
            },
        )
    
    color = ColorRepository.create_from_request(db, DEFAULT_TENANT_ID, request)
    logger.info("color_created", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "color_id": str(color.id),
        "code": color.code,
    })
    return color


@router.get("/{code}", response_model=ColorResponse)
def get_color(
    code: str,
    db: Session = Depends(get_db),
):
    """Get color by code."""
    logger.info("get_color", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    color = ColorRepository.get_by_code(db, DEFAULT_TENANT_ID, code)
    if not color:
        logger.warning("color_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COLOR_NOT_FOUND",
                "message": f"Color '{code}' not found",
            },
        )
    return color


@router.put("/{code}", response_model=ColorResponse)
def update_color(
    code: str,
    request: ColorUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a color by code."""
    logger.info("update_color", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    color = ColorRepository.update_from_request(db, DEFAULT_TENANT_ID, code, request)
    if not color:
        logger.warning("color_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COLOR_NOT_FOUND",
                "message": f"Color '{code}' not found",
            },
        )
    
    logger.info("color_updated", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    return color


@router.delete("/{code}", status_code=204)
def delete_color(
    code: str,
    db: Session = Depends(get_db),
):
    """Delete (deactivate) a color by code."""
    logger.info("delete_color", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
    
    success = ColorRepository.soft_delete(db, DEFAULT_TENANT_ID, code)
    if not success:
        logger.warning("color_not_found", extra={
            "tenant_id": str(DEFAULT_TENANT_ID),
            "code": code,
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COLOR_NOT_FOUND",
                "message": f"Color '{code}' not found",
            },
        )
    
    logger.info("color_deleted", extra={
        "tenant_id": str(DEFAULT_TENANT_ID),
        "code": code,
    })
