"""Repository for order tags and assignments."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database import OrderTagAssignmentModel, OrderTagLinkModel, OrderTagModel


class OrderTagRepository:
    """CRUD helpers for reusable order tags scoped by global/event."""

    @staticmethod
    def _clean_name(name: str) -> str:
        return (name or "").strip()

    @staticmethod
    def _key(name: str) -> str:
        return OrderTagRepository._clean_name(name).lower()

    @staticmethod
    def _ensure_schema(db: Session) -> None:
        """Create tag tables on demand when schema is behind deployment code."""
        bind = db.get_bind()
        OrderTagModel.__table__.create(bind=bind, checkfirst=True)
        OrderTagAssignmentModel.__table__.create(bind=bind, checkfirst=True)
        OrderTagLinkModel.__table__.create(bind=bind, checkfirst=True)

    @staticmethod
    def list_tags(db: Session, tenant_id: UUID, scope_key: str, event_id: Optional[UUID]) -> List[OrderTagModel]:
        OrderTagRepository._ensure_schema(db)
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
        try:
            db.add(row)
            db.flush()
            return row
        except IntegrityError:
            # Concurrent requests may create the same tag at the same time.
            db.rollback()
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
            raise

    @staticmethod
    def add_tag_by_name(
        db: Session,
        tenant_id: UUID,
        scope_key: str,
        event_id: Optional[UUID],
        bling_order_id: int,
        tag_name: str,
    ) -> List[str]:
        OrderTagRepository._ensure_schema(db)
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
            try:
                db.add(link)
                db.flush()
            except IntegrityError:
                # Idempotent behavior when duplicate link is inserted concurrently.
                db.rollback()

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
        OrderTagRepository._ensure_schema(db)
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
        OrderTagRepository._ensure_schema(db)
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
        OrderTagRepository._ensure_schema(db)
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
