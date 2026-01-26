"""Repository for Bling tokens."""
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from app.models.database import BlingTokenModel, TenantModel
from app.infra.logging import get_logger

logger = get_logger(__name__)


class BlingTokenRepository:
    """Repository for managing Bling OAuth2 tokens."""

    @staticmethod
    def create_or_update(
        db: Session,
        tenant_id: UUID,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        scope: str = None,
        token_type: str = "Bearer",
    ) -> BlingTokenModel:
        """Create or update Bling token."""
        
        existing_token = db.query(BlingTokenModel).filter(
            BlingTokenModel.tenant_id == tenant_id
        ).first()

        logger.info(
            "token_save tenant_id=%s action=%s",
            str(tenant_id),
            "update" if existing_token else "create",
        )

        if existing_token:
            existing_token.access_token = access_token
            existing_token.refresh_token = refresh_token
            existing_token.expires_at = expires_at
            existing_token.token_type = token_type
            existing_token.scope = scope
            existing_token.updated_at = datetime.utcnow()
            db.add(existing_token)
        else:
            new_token = BlingTokenModel(
                tenant_id=tenant_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                token_type=token_type,
                scope=scope,
            )
            db.add(new_token)

        db.commit()
        return existing_token if existing_token else new_token

    @staticmethod
    def get_by_tenant(db: Session, tenant_id: UUID) -> BlingTokenModel:
        """Get Bling token by tenant."""
        return db.query(BlingTokenModel).filter(
            BlingTokenModel.tenant_id == tenant_id
        ).first()

    @staticmethod
    def get_or_create_default_tenant(db: Session) -> TenantModel:
        """Get or create default tenant for single-tenant setup."""
        # In Sprint 1, we use a single default tenant
        FIXED_TENANT_ID = "00000000-0000-0000-0000-000000000001"
        
        existing = db.query(TenantModel).filter(
            TenantModel.id == FIXED_TENANT_ID
        ).first()

        if existing:
            return existing

        default_tenant = TenantModel(
            id=FIXED_TENANT_ID,
            name="Default Tenant",
        )
        db.add(default_tenant)
        db.commit()
        return default_tenant
