"""Repository for Model CRUD operations."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.database import ModelModel
from app.models.schemas import ModelCreateRequest, ModelUpdateRequest


class ModelRepository:
    """Repository for managing models."""

    @staticmethod
    def create(db: Session, tenant_id: UUID, request: ModelCreateRequest) -> ModelModel:
        """Create a new model."""
        model = ModelModel(
            tenant_id=tenant_id,
            code=request.code,
            name=request.name,
            allowed_sizes=request.allowed_sizes,
            size_order=request.size_order or request.allowed_sizes,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def get_by_code(db: Session, tenant_id: UUID, code: str) -> Optional[ModelModel]:
        """Get model by code."""
        return db.query(ModelModel).filter(
            ModelModel.tenant_id == tenant_id,
            ModelModel.code == code,
        ).first()

    @staticmethod
    def get_by_id(db: Session, tenant_id: UUID, model_id: UUID) -> Optional[ModelModel]:
        """Get model by ID."""
        return db.query(ModelModel).filter(
            ModelModel.tenant_id == tenant_id,
            ModelModel.id == model_id,
        ).first()

    @staticmethod
    def list_active(db: Session, tenant_id: UUID) -> List[ModelModel]:
        """List active models."""
        return db.query(ModelModel).filter(
            ModelModel.tenant_id == tenant_id,
            ModelModel.is_active == True,
        ).order_by(ModelModel.created_at.desc()).all()

    @staticmethod
    def list_all(db: Session, tenant_id: UUID) -> List[ModelModel]:
        """List all models (active and inactive)."""
        return db.query(ModelModel).filter(
            ModelModel.tenant_id == tenant_id,
        ).order_by(ModelModel.created_at.desc()).all()

    @staticmethod
    def update(db: Session, tenant_id: UUID, code: str, request: ModelUpdateRequest) -> Optional[ModelModel]:
        """Update a model."""
        model = ModelRepository.get_by_code(db, tenant_id, code)
        if not model:
            return None

        if request.name is not None:
            model.name = request.name
        if request.allowed_sizes is not None:
            model.allowed_sizes = request.allowed_sizes
            # If size_order wasn't explicitly provided, reset it to allowed_sizes
            if request.size_order is None:
                model.size_order = request.allowed_sizes
        if request.size_order is not None:
            model.size_order = request.size_order
        if request.is_active is not None:
            model.is_active = request.is_active

        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def delete(db: Session, tenant_id: UUID, code: str) -> bool:
        """Delete a model (soft delete via is_active)."""
        model = ModelRepository.get_by_code(db, tenant_id, code)
        if not model:
            return False
        model.is_active = False
        db.commit()
        return True
