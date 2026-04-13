"""Repository for sync scope versions (used for cross-device synchronization)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.database import SyncScopeVersionModel


# Scope key constants
SCOPE_ORDERS_GLOBAL = "orders:global"


def scope_event_sales(event_id: UUID) -> str:
    """Generate scope key for event sales."""
    return f"event_sales:{event_id}"


class SyncScopeVersionRepository:
    """Repository for managing sync scope versions."""

    @staticmethod
    def get_scope_version(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
    ) -> Optional[SyncScopeVersionModel]:
        """Get or create a sync scope version row."""
        row = (
            db.query(SyncScopeVersionModel)
            .filter(
                SyncScopeVersionModel.tenant_id == tenant_id,
                SyncScopeVersionModel.scope_key == scope_key,
            )
            .first()
        )
        if not row:
            # Create with version 0
            row = SyncScopeVersionModel(
                tenant_id=tenant_id,
                scope_key=scope_key,
                version=0,
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    @staticmethod
    def bump_scope(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
    ) -> SyncScopeVersionModel:
        """Increment version for a scope."""
        row = SyncScopeVersionRepository.get_scope_version(db, tenant_id, scope_key)
        row.version += 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row
