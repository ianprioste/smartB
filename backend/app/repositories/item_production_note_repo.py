"""Repository for item production notes (persistent across Bling syncs)."""
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
