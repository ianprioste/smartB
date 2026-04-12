"""Repository for SQL-based sync versions used by frontend delta polling."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.database import SyncScopeVersionModel
from app.utils.datetime_utils import now_local

SCOPE_ORDERS_GLOBAL = "orders_global"


def scope_event_sales(event_id: UUID) -> str:
    return f"event_sales:{event_id}"


class SyncScopeVersionRepository:
    @staticmethod
    def get_scope_version(db: Session, tenant_id: UUID, scope_key: str) -> SyncScopeVersionModel | None:
        return (
            db.query(SyncScopeVersionModel)
            .filter(
                SyncScopeVersionModel.tenant_id == tenant_id,
                SyncScopeVersionModel.scope_key == scope_key,
            )
            .first()
        )

    @staticmethod
    def bump_scope(db: Session, tenant_id: UUID, scope_key: str) -> SyncScopeVersionModel:
        """Increment version for a tenant scope, creating it when absent."""
        now = now_local()
        row = SyncScopeVersionRepository.get_scope_version(db, tenant_id, scope_key)
        if row is None:
            row = SyncScopeVersionModel(
                tenant_id=tenant_id,
                scope_key=scope_key,
                version=1,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            return row

        row.version = int(row.version or 0) + 1
        row.updated_at = now
        return row
