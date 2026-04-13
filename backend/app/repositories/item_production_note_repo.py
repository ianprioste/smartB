"""Repository for item production notes (persistent across Bling syncs)."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import ItemProductionNoteModel


class ItemProductionNoteRepository:

    @staticmethod
    def get_all_for_event(db: Session, tenant_id: UUID, event_id: UUID) -> List[ItemProductionNoteModel]:
        return (
            db.query(ItemProductionNoteModel)
            .filter(
                ItemProductionNoteModel.tenant_id == tenant_id,
                ItemProductionNoteModel.event_id == event_id,
            )
            .all()
        )

    @staticmethod
    def get_latest_by_sku(db: Session, tenant_id: UUID) -> Dict[str, "ItemProductionNoteModel"]:
        """Return a dict {sku_upper: note} with the most recently updated note per SKU across all events."""
        # Sub-query: max updated_at per (tenant, sku)
        sub = (
            db.query(
                ItemProductionNoteModel.sku,
                func.max(ItemProductionNoteModel.updated_at).label("max_upd"),
            )
            .filter(ItemProductionNoteModel.tenant_id == tenant_id)
            .group_by(ItemProductionNoteModel.sku)
            .subquery()
        )
        rows = (
            db.query(ItemProductionNoteModel)
            .join(
                sub,
                (ItemProductionNoteModel.sku == sub.c.sku)
                & (ItemProductionNoteModel.updated_at == sub.c.max_upd),
            )
            .filter(ItemProductionNoteModel.tenant_id == tenant_id)
            .all()
        )
        return {r.sku.strip().upper(): r for r in rows}

    @staticmethod
    def upsert(
        db: Session,
        tenant_id: UUID,
        event_id: UUID,
        sku: str,
        production_status: str,
        notes: Optional[str],
        bling_order_id: Optional[int] = None,
        preserve_existing_notes: bool = False,
    ) -> ItemProductionNoteModel:
        filters = [
            ItemProductionNoteModel.tenant_id == tenant_id,
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == sku,
        ]
        if bling_order_id is not None:
            filters.append(ItemProductionNoteModel.bling_order_id == bling_order_id)
        else:
            filters.append(ItemProductionNoteModel.bling_order_id.is_(None))
        row = db.query(ItemProductionNoteModel).filter(*filters).first()
        if row:
            row.production_status = production_status
            if not preserve_existing_notes:
                row.notes = notes
        else:
            row = ItemProductionNoteModel(
                tenant_id=tenant_id,
                event_id=event_id,
                sku=sku,
                bling_order_id=bling_order_id,
                production_status=production_status,
                notes=notes,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_updated_since(
        db: Session,
        tenant_id: UUID,
        since: datetime,
        event_id: Optional[UUID] = None,
    ) -> List[ItemProductionNoteModel]:
        query = (
            db.query(ItemProductionNoteModel)
            .filter(
                ItemProductionNoteModel.tenant_id == tenant_id,
                ItemProductionNoteModel.updated_at > since,
            )
            .order_by(ItemProductionNoteModel.updated_at.asc())
        )
        if event_id is not None:
            query = query.filter(ItemProductionNoteModel.event_id == event_id)
        return query.all()

    @staticmethod
    def list_campaign_order_ids(db: Session, tenant_id: UUID) -> set[int]:
        """Return Bling order IDs that are already linked to campaigns."""
        rows = (
            db.query(ItemProductionNoteModel.bling_order_id)
            .filter(
                ItemProductionNoteModel.tenant_id == tenant_id,
                ItemProductionNoteModel.bling_order_id.isnot(None),
            )
            .distinct()
            .all()
        )
        return {int(row[0]) for row in rows if row and row[0] is not None}
