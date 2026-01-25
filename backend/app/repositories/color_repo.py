"""Repository for Color CRUD operations - Refactored with BaseRepository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.database import ColorModel
from app.models.schemas import ColorCreateRequest, ColorUpdateRequest
from app.repositories.base import BaseRepository


class ColorRepository(BaseRepository[ColorModel]):
    """Repository for managing colors with common CRUD operations."""
    
    model_class = ColorModel
    
    @classmethod
    def create_from_request(
        cls,
        db: Session,
        tenant_id: UUID,
        request: ColorCreateRequest
    ) -> ColorModel:
        """
        Create a new color from request data.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Color creation request
            
        Returns:
            Created ColorModel instance
        """
        return cls.create(
            db,
            tenant_id=tenant_id,
            code=request.code,
            name=request.name,
        )
    
    @classmethod
    def get_by_code(
        cls,
        db: Session,
        tenant_id: UUID,
        code: str
    ) -> Optional[ColorModel]:
        """
        Get color by code.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Color code
            
        Returns:
            ColorModel or None if not found
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
    ) -> List[ColorModel]:
        """
        List active colors.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            
        Returns:
            List of active colors ordered by creation date
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
        request: ColorUpdateRequest
    ) -> Optional[ColorModel]:
        """
        Update a color from request data.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Color code to update
            request: Update request with new values
            
        Returns:
            Updated ColorModel or None if not found
        """
        color = cls.get_by_code(db, tenant_id, code)
        if not color:
            return None
        
        if request.name is not None:
            color.name = request.name
        
        if request.is_active is not None:
            color.is_active = request.is_active
        
        db.commit()
        db.refresh(color)
        return color
    
    @classmethod
    def soft_delete(
        cls,
        db: Session,
        tenant_id: UUID,
        code: str
    ) -> bool:
        """
        Soft delete a color (mark as inactive).
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            code: Color code to delete
            
        Returns:
            True if deleted, False if not found
        """
        color = cls.get_by_code(db, tenant_id, code)
        if not color:
            return False
        
        color.is_active = False
        db.commit()
        return True
