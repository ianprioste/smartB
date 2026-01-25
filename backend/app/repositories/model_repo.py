"""Repository for Model CRUD operations - Refactored with BaseRepository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.database import ModelModel
from app.models.schemas import ModelCreateRequest, ModelUpdateRequest
from app.repositories.base import BaseRepository


class ModelRepository(BaseRepository[ModelModel]):
    """Repository for managing models with common CRUD operations."""
    
    model_class = ModelModel
    
    @classmethod
    def create_from_request(
        cls,
        db: Session,
        tenant_id: UUID,
        request: ModelCreateRequest
    ) -> ModelModel:
        """
        Create a new model from request data.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Model creation request
            
        Returns:
            Created ModelModel instance
        """
        return cls.create(
            db,
            tenant_id=tenant_id,
            code=request.code,
            name=request.name,
            allowed_sizes=request.allowed_sizes,
            size_order=request.size_order or request.allowed_sizes,
        )
    
    @classmethod
    def get_by_code(
        cls,
        db: Session,
        tenant_id: UUID,
        code: str
    ) -> Optional[ModelModel]:
        """
        Get model by code.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Model code
            
        Returns:
            ModelModel or None if not found
        """
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.code == code,
        ).first()
    
    @classmethod
    def list_active(
        cls,
        db: Session,
        tenant_id: UUID
    ) -> List[ModelModel]:
        """
        List active models.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            
        Returns:
            List of active models ordered by creation date
        """
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.is_active == True,
        ).order_by(cls.model_class.created_at.desc()).all()
    
    @classmethod
    def update_from_request(
        cls,
        db: Session,
        tenant_id: UUID,
        code: str,
        request: ModelUpdateRequest
    ) -> Optional[ModelModel]:
        """
        Update a model from request data.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Model code to update
            request: Update request with new values
            
        Returns:
            Updated ModelModel or None if not found
        """
        model = cls.get_by_code(db, tenant_id, code)
        if not model:
            return None
        
        # Update only provided fields
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
    
    @classmethod
    def soft_delete(
        cls,
        db: Session,
        tenant_id: UUID,
        code: str
    ) -> bool:
        """
        Soft delete a model (mark as inactive).
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Model code to delete
            
        Returns:
            True if deleted, False if not found
        """
        model = cls.get_by_code(db, tenant_id, code)
        if not model:
            return False
        
        model.is_active = False
        db.commit()
        return True
