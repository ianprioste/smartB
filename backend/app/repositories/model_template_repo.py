"""Repository for ModelTemplate CRUD operations."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.database import ModelTemplateModel
from app.models.schemas import ModelTemplateCreateRequest
from app.models.enums import TemplateKindEnum


class ModelTemplateRepository:
    """Repository for managing model templates."""

    @staticmethod
    def create(
        db: Session,
        tenant_id: UUID,
        request: ModelTemplateCreateRequest,
        bling_product_sku: str,
        bling_product_name: Optional[str] = None,
    ) -> ModelTemplateModel:
        """Create a new model template."""
        template = ModelTemplateModel(
            tenant_id=tenant_id,
            model_code=request.model_code,
            template_kind=request.template_kind,
            bling_product_id=request.bling_product_id,
            bling_product_sku=bling_product_sku,
            bling_product_name=bling_product_name,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def get_by_id(db: Session, tenant_id: UUID, template_id: UUID) -> Optional[ModelTemplateModel]:
        """Get template by ID."""
        return db.query(ModelTemplateModel).filter(
            ModelTemplateModel.tenant_id == tenant_id,
            ModelTemplateModel.id == template_id,
        ).first()

    @staticmethod
    def get_by_model_and_kind(
        db: Session,
        tenant_id: UUID,
        model_code: str,
        template_kind: str,
    ) -> Optional[ModelTemplateModel]:
        """Get template by model code and kind."""
        return db.query(ModelTemplateModel).filter(
            ModelTemplateModel.tenant_id == tenant_id,
            ModelTemplateModel.model_code == model_code,
            ModelTemplateModel.template_kind == template_kind,
        ).first()

    @staticmethod
    def list_by_model(db: Session, tenant_id: UUID, model_code: str) -> List[ModelTemplateModel]:
        """List all templates for a model."""
        return db.query(ModelTemplateModel).filter(
            ModelTemplateModel.tenant_id == tenant_id,
            ModelTemplateModel.model_code == model_code,
        ).order_by(ModelTemplateModel.template_kind).all()

    @staticmethod
    def list_all(db: Session, tenant_id: UUID) -> List[ModelTemplateModel]:
        """List all templates for tenant."""
        return db.query(ModelTemplateModel).filter(
            ModelTemplateModel.tenant_id == tenant_id,
        ).order_by(ModelTemplateModel.model_code, ModelTemplateModel.template_kind).all()

    @staticmethod
    def delete(db: Session, tenant_id: UUID, template_id: UUID) -> bool:
        """Delete a template."""
        template = ModelTemplateRepository.get_by_id(db, tenant_id, template_id)
        if not template:
            return False
        db.delete(template)
        db.commit()
        return True

    @staticmethod
    def delete_by_model_and_kind(db: Session, tenant_id: UUID, model_code: str, template_kind: str) -> bool:
        """Delete a template by model code and kind."""
        template = ModelTemplateRepository.get_by_model_and_kind(db, tenant_id, model_code, template_kind)
        if not template:
            return False
        db.delete(template)
        db.commit()
        return True
