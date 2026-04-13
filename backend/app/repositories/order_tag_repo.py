"""Repository for order tags and assignments."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.database import OrderTagLinkModel, OrderTagModel


class OrderTagRepository:
    """CRUD helpers for reusable order tags scoped by global/event."""

    @staticmethod
    def _clean_name(name: str) -> str:
        return (name or "").strip()

    @staticmethod
    def _key(name: str) -> str:
        return OrderTagRepository._clean_name(name).lower()

    @staticmethod
    def list_tags(db: Session, tenant_id: UUID, scope_key: str, event_id: Optional[UUID]) -> List[OrderTagModel]:
        return (
            db.query(OrderTagModel)
            .filter(
                OrderTagModel.tenant_id == tenant_id,
                OrderTagModel.scope_key == scope_key,
                OrderTagModel.event_id == event_id,
            )
            .order_by(OrderTagModel.name.asc())
            .all()
        )

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

        tags = OrderTagRepository.list_tags(db, tenant_id, scope_key, event_id)
        tag_names = [t.name for t in tags if OrderTagRepository._get_assignment_count(db, t.id, bling_order_id) > 0]
        return tag_names

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
            tags = OrderTagRepository.list_tags(db, tenant_id, scope_key, event_id)
            tag_names = [t.name for t in tags if OrderTagRepository._get_assignment_count(db, t.id, bling_order_id) > 0]
            return tag_names

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

        tags = OrderTagRepository.list_tags(db, tenant_id, scope_key, event_id)
        tag_names = [t.name for t in tags if OrderTagRepository._get_assignment_count(db, t.id, bling_order_id) > 0]
        return tag_names

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

    @staticmethod
    def _get_assignment_count(db: Session, tag_id: UUID, bling_order_id: int) -> int:
        return (
            db.query(OrderTagLinkModel)
            .filter(
                OrderTagLinkModel.tag_id == tag_id,
                OrderTagLinkModel.bling_order_id == int(bling_order_id),
            )
            .count()
        )
