"""Repository for Color CRUD operations."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.database import ColorModel
from app.models.schemas import ColorCreateRequest, ColorUpdateRequest


class ColorRepository:
    """Repository for managing colors."""

    @staticmethod
    def create(db: Session, tenant_id: UUID, request: ColorCreateRequest) -> ColorModel:
        """Create a new color."""
        color = ColorModel(
            tenant_id=tenant_id,
            code=request.code,
            name=request.name,
        )
        db.add(color)
        db.commit()
        db.refresh(color)
        return color

    @staticmethod
    def get_by_code(db: Session, tenant_id: UUID, code: str) -> Optional[ColorModel]:
        """Get color by code."""
        return db.query(ColorModel).filter(
            ColorModel.tenant_id == tenant_id,
            ColorModel.code == code,
        ).first()

    @staticmethod
    def get_by_id(db: Session, tenant_id: UUID, color_id: UUID) -> Optional[ColorModel]:
        """Get color by ID."""
        return db.query(ColorModel).filter(
            ColorModel.tenant_id == tenant_id,
            ColorModel.id == color_id,
        ).first()

    @staticmethod
    def list_active(db: Session, tenant_id: UUID) -> List[ColorModel]:
        """List active colors."""
        return db.query(ColorModel).filter(
            ColorModel.tenant_id == tenant_id,
            ColorModel.is_active == True,
        ).order_by(ColorModel.created_at.desc()).all()

    @staticmethod
    def list_all(db: Session, tenant_id: UUID) -> List[ColorModel]:
        """List all colors (active and inactive)."""
        return db.query(ColorModel).filter(
            ColorModel.tenant_id == tenant_id,
        ).order_by(ColorModel.created_at.desc()).all()

    @staticmethod
    def update(db: Session, tenant_id: UUID, code: str, request: ColorUpdateRequest) -> Optional[ColorModel]:
        """Update a color."""
        color = ColorRepository.get_by_code(db, tenant_id, code)
        if not color:
            return None

        if request.name is not None:
            color.name = request.name
        if request.is_active is not None:
            color.is_active = request.is_active

        db.commit()
        db.refresh(color)
        return color

    @staticmethod
    def delete(db: Session, tenant_id: UUID, code: str) -> bool:
        """Delete a color (soft delete via is_active)."""
        color = ColorRepository.get_by_code(db, tenant_id, code)
        if not color:
            return False
        color.is_active = False
        db.commit()
        return True
