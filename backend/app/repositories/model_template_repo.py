"""Repository for ModelTemplate CRUD operations - Refactored with BaseRepository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.database import ModelTemplateModel
from app.models.schemas import ModelTemplateCreateRequest
from app.repositories.base import BaseRepository


class ModelTemplateRepository(BaseRepository[ModelTemplateModel]):
    """Repository for managing model templates with common CRUD operations."""
    
    model_class = ModelTemplateModel
    
    @classmethod
    def create_from_request(
        cls,
        db: Session,
        tenant_id: UUID,
        request: ModelTemplateCreateRequest,
        bling_product_sku: str,
        bling_product_name: Optional[str] = None,
    ) -> ModelTemplateModel:
        """
        Create a new model template from request data.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Template creation request
            bling_product_sku: SKU from Bling
            bling_product_name: Name from Bling
            
        Returns:
            Created ModelTemplateModel instance
        """
        return cls.create(
            db,
            tenant_id=tenant_id,
            model_code=request.model_code,
            template_kind=request.template_kind,
            bling_product_id=request.bling_product_id,
            bling_product_sku=bling_product_sku,
            bling_product_name=bling_product_name,
        )
    
    @classmethod
    def create_or_update(
        cls,
        db: Session,
        tenant_id: UUID,
        request: ModelTemplateCreateRequest,
        bling_product_sku: str,
        bling_product_name: Optional[str] = None,
    ) -> ModelTemplateModel:
        """
        Create new template or update existing one (upsert).
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            request: Template creation request
            bling_product_sku: SKU from Bling
            bling_product_name: Name from Bling
            
        Returns:
            Created or updated ModelTemplateModel instance
        """
        existing = cls.get_by_model_and_kind(
            db, tenant_id, request.model_code, request.template_kind
        )
        
        if existing:
            # Update existing template
            existing.bling_product_id = request.bling_product_id
            existing.bling_product_sku = bling_product_sku
            existing.bling_product_name = bling_product_name
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new template
            return cls.create_from_request(
                db, tenant_id, request, bling_product_sku, bling_product_name
            )
    
    @classmethod
    def get_by_model_and_kind(
        cls,
        db: Session,
        tenant_id: UUID,
        model_code: str,
        template_kind: str,
    ) -> Optional[ModelTemplateModel]:
        """
        Get template by model code and kind.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            model_code: Model code
            template_kind: Template kind
            
        Returns:
            ModelTemplateModel or None if not found
        """
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.model_code == model_code,
            cls.model_class.template_kind == template_kind,
        ).first()
    
    @classmethod
    def list_by_model(
        cls,
        db: Session,
        tenant_id: UUID,
        model_code: str
    ) -> List[ModelTemplateModel]:
        """
        List all templates for a model.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            model_code: Model code
            
        Returns:
            List of templates ordered by kind
        """
        return db.query(cls.model_class).filter(
            cls.model_class.tenant_id == tenant_id,
            cls.model_class.model_code == model_code,
        ).order_by(cls.model_class.template_kind).all()
    
    @classmethod
    def delete_by_model_and_kind(
        cls,
        db: Session,
        tenant_id: UUID,
        model_code: str,
        template_kind: str
    ) -> bool:
        """
        Delete a template by model code and kind.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            model_code: Model code
            template_kind: Template kind
            
        Returns:
            True if deleted, False if not found
        """
        template = cls.get_by_model_and_kind(db, tenant_id, model_code, template_kind)
        if not template:
            return False
        
        db.delete(template)
        db.commit()
        return True
