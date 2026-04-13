"""Repository for order tags and assignments."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.database import OrderTagLinkModel, OrderTagModel


class OrderTagSchemaError(RuntimeError):
    """Raised when order tag tables are unavailable and cannot be created."""


class OrderTagRepository:
    """CRUD helpers for reusable order tags scoped by global/event."""

    @staticmethod
    def _clean_name(name: str) -> str:
        return (name or "").strip()

    @staticmethod
    def _key(name: str) -> str:
        return OrderTagRepository._clean_name(name).lower()

    @staticmethod
    def _ensure_column_exists(bind, inspector, table_name: str, column_name: str, ddl_sql: str) -> None:
        existing = {col.get("name") for col in inspector.get_columns(table_name)}
        if column_name in existing:
            return
        bind.execute(sa.text(ddl_sql))

    @staticmethod
    def _try_ensure_schema(db: Session) -> None:
        """Ensure order tag tables exist, otherwise raise a clear schema error."""
        bind = db.get_bind()
        inspector = sa.inspect(bind)
        missing = [table for table in ("order_tags", "order_tag_links") if not inspector.has_table(table)]
        if not missing:
            return

        try:
            OrderTagModel.__table__.create(bind=bind, checkfirst=True)
            OrderTagLinkModel.__table__.create(bind=bind, checkfirst=True)
        except Exception as exc:
            raise OrderTagSchemaError(
                "Schema de tags indisponivel. Rode a migration 011 (alembic upgrade head)."
            ) from exc

        # Validate again so permission-restricted environments fail explicitly.
        inspector = sa.inspect(bind)
        still_missing = [table for table in ("order_tags", "order_tag_links") if not inspector.has_table(table)]
        if still_missing:
            raise OrderTagSchemaError(
                "Schema de tags ausente apos tentativa de criacao. Rode alembic upgrade head com usuario de banco com DDL."
            )

        # Heal partial/legacy schemas where tables exist but columns were not fully created.
        inspector = sa.inspect(bind)
        if bind.dialect.name == "postgresql":
            dt_sql = "TIMESTAMP WITHOUT TIME ZONE"
        else:
            dt_sql = "DATETIME"

        try:
            OrderTagRepository._ensure_column_exists(
                bind,
                inspector,
                "order_tags",
                "name_key",
                "ALTER TABLE order_tags ADD COLUMN name_key VARCHAR(80)",
            )
            OrderTagRepository._ensure_column_exists(
                bind,
                inspector,
                "order_tags",
                "created_at",
                f"ALTER TABLE order_tags ADD COLUMN created_at {dt_sql}",
            )
            OrderTagRepository._ensure_column_exists(
                bind,
                inspector,
                "order_tags",
                "updated_at",
                f"ALTER TABLE order_tags ADD COLUMN updated_at {dt_sql}",
            )
            OrderTagRepository._ensure_column_exists(
                bind,
                inspector,
                "order_tag_links",
                "created_at",
                f"ALTER TABLE order_tag_links ADD COLUMN created_at {dt_sql}",
            )
            OrderTagRepository._ensure_column_exists(
                bind,
                inspector,
                "order_tag_links",
                "updated_at",
                f"ALTER TABLE order_tag_links ADD COLUMN updated_at {dt_sql}",
            )
        except Exception as exc:
            raise OrderTagSchemaError(
                "Schema de tags incompleto (colunas ausentes). Rode alembic upgrade head para corrigir."
            ) from exc

    @staticmethod
    def list_tags(db: Session, tenant_id: UUID, scope_key: str, event_id: Optional[UUID]) -> List[OrderTagModel]:
        # Only list tags that are currently assigned to at least one order in the same scope.
        return (
            db.query(OrderTagModel)
            .join(
                OrderTagLinkModel,
                and_(
                    OrderTagLinkModel.tag_id == OrderTagModel.id,
                    OrderTagLinkModel.tenant_id == tenant_id,
                    OrderTagLinkModel.scope_key == scope_key,
                    OrderTagLinkModel.event_id == event_id,
                ),
            )
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
            )
            .distinct()
            .order_by(OrderTagModel.name.asc())
            .all()
        )

    @staticmethod
    def _tags_for_order(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_id: int,
    ) -> List[str]:
        rows = (
            db.query(OrderTagModel.name)
            .join(
                OrderTagLinkModel,
                OrderTagLinkModel.tag_id == OrderTagModel.id,
            )
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
                OrderTagLinkModel.tenant_id == tenant_id,
                OrderTagLinkModel.scope_key == scope_key,
                OrderTagLinkModel.event_id == event_id,
                OrderTagLinkModel.bling_order_id == int(bling_order_id),
            )
            .order_by(OrderTagModel.name.asc())
            .all()
        )
        return [name for (name,) in rows if name]

    @staticmethod
    def _cleanup_orphan_tags(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
    ) -> None:
        orphan_ids = (
            db.query(OrderTagModel.id)
            .outerjoin(
                OrderTagLinkModel,
                and_(
                    OrderTagLinkModel.tag_id == OrderTagModel.id,
                    OrderTagLinkModel.tenant_id == tenant_id,
                    OrderTagLinkModel.scope_key == scope_key,
                    OrderTagLinkModel.event_id == event_id,
                ),
            )
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
                OrderTagLinkModel.id.is_(None),
            )
            .all()
        )

        orphan_ids = [tag_id for (tag_id,) in orphan_ids]
        if orphan_ids:
            db.query(OrderTagModel).filter(OrderTagModel.id.in_(orphan_ids)).delete(synchronize_session=False)
            db.flush()

    @staticmethod
    def get_or_create_tag(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        tag_name: str,
    ) -> OrderTagModel:
        clean_name = OrderTagRepository._clean_name(tag_name)
        if not clean_name:
            raise ValueError("Tag name cannot be empty")
        name_key = OrderTagRepository._key(clean_name)

        existing = (
            db.query(OrderTagModel)
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
                OrderTagModel.name_key == name_key,
            )
            .first()
        )
        if existing:
            return existing

        row = OrderTagModel(
            tenant_id=tenant_id,
            scope_key=scope_key,
            event_id=event_id,
            name=clean_name,
            name_key=name_key,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def add_tag_by_name(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_id: int,
        tag_name: str,
    ) -> List[str]:
        OrderTagRepository._try_ensure_schema(db)
        tag = OrderTagRepository.get_or_create_tag(
            db=db,
            tenant_id=tenant_id,
            scope_key=scope_key,
            event_id=event_id,
            tag_name=tag_name,
        )

        existing = (
            db.query(OrderTagLinkModel)
            .filter(
                OrderTagLinkModel.tenant_id == tenant_id,
                OrderTagLinkModel.scope_key == scope_key,
                OrderTagLinkModel.event_id == event_id,
                OrderTagLinkModel.bling_order_id == int(bling_order_id),
                OrderTagLinkModel.tag_id == tag.id,
            )
            .first()
        )
        if not existing:
            link = OrderTagLinkModel(
                tenant_id=tenant_id,
                scope_key=scope_key,
                event_id=event_id,
                bling_order_id=int(bling_order_id),
                tag_id=tag.id,
            )
            db.add(link)
            db.flush()

        return OrderTagRepository._tags_for_order(db, tenant_id, scope_key, event_id, bling_order_id)

    @staticmethod
    def remove_tag_by_name(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_id: int,
        tag_name: str,
    ) -> List[str]:
        clean_name = OrderTagRepository._clean_name(tag_name)
        name_key = OrderTagRepository._key(clean_name)

        tag = (
            db.query(OrderTagModel)
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
                OrderTagModel.name_key == name_key,
            )
            .first()
        )
        if not tag:
            return OrderTagRepository._tags_for_order(db, tenant_id, scope_key, event_id, bling_order_id)

        link = (
            db.query(OrderTagLinkModel)
            .filter(
                OrderTagLinkModel.tenant_id == tenant_id,
                OrderTagLinkModel.scope_key == scope_key,
                OrderTagLinkModel.event_id == event_id,
                OrderTagLinkModel.bling_order_id == int(bling_order_id),
                OrderTagLinkModel.tag_id == tag.id,
            )
            .first()
        )
        if link:
            db.delete(link)
            db.flush()

        OrderTagRepository._cleanup_orphan_tags(db, tenant_id, scope_key, event_id)
        return OrderTagRepository._tags_for_order(db, tenant_id, scope_key, event_id, bling_order_id)

    @staticmethod
    def clear_assignment(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_id: int,
    ) -> None:
        db.query(OrderTagLinkModel).filter(
            OrderTagLinkModel.tenant_id == tenant_id,
            OrderTagLinkModel.scope_key == scope_key,
            OrderTagLinkModel.event_id == event_id,
            OrderTagLinkModel.bling_order_id == int(bling_order_id),
        ).delete()
        db.flush()
        OrderTagRepository._cleanup_orphan_tags(db, tenant_id, scope_key, event_id)

    @staticmethod
    def get_assignments_map(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_ids: Iterable[int],
    ) -> Dict[int, List[str]]:
        """Return map of bling_order_id -> list of tag names."""
        links = (
            db.query(OrderTagLinkModel)
            .filter(
                OrderTagLinkModel.tenant_id == tenant_id,
                OrderTagLinkModel.scope_key == scope_key,
                OrderTagLinkModel.event_id == event_id,
                OrderTagLinkModel.bling_order_id.in_(bling_order_ids),
            )
            .all()
        )

        tag_map = defaultdict(list)
        for link in links:
            tag = db.query(OrderTagModel).filter(OrderTagModel.id == link.tag_id).first()
            if tag:
                tag_map[link.bling_order_id].append(tag.name)

        return dict(tag_map)
