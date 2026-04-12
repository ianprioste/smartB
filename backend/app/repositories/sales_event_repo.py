"""Repository helpers for sales events."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.database import SalesEventModel, SalesEventProductModel


def _ensure_is_active_column(db: Session) -> None:
    """Add is_active column if missing (guard for environments where migration 009 hasn't run)."""
    from sqlalchemy.exc import OperationalError
    try:
        db.execute(text("SELECT is_active FROM sales_events LIMIT 1"))
        db.rollback()
    except OperationalError:
        db.rollback()
        try:
            db.execute(text("ALTER TABLE sales_events ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            db.commit()
        except Exception:
            db.rollback()


class SalesEventRepository:
    """CRUD operations for sales events and related products."""

    @staticmethod
    def create(
        db: Session,
        tenant_id: UUID,
        name: str,
        start_date,
        end_date,
        products: List[dict],
    ) -> SalesEventModel:
        event = SalesEventModel(
            tenant_id=tenant_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
        )
        db.add(event)
        db.flush()

        for product in products:
            db.add(
                SalesEventProductModel(
                    event_id=event.id,
                    bling_product_id=product.get("bling_product_id"),
                    sku=(product.get("sku") or "").strip().upper(),
                    product_name=product.get("product_name"),
                )
            )

        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_by_id(db: Session, event_id: UUID, tenant_id: UUID) -> Optional[SalesEventModel]:
        _ensure_is_active_column(db)
        return (
            db.query(SalesEventModel)
            .filter(
                SalesEventModel.id == event_id,
                SalesEventModel.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def list_by_tenant(db: Session, tenant_id: UUID) -> List[SalesEventModel]:
        _ensure_is_active_column(db)
        return (
            db.query(SalesEventModel)
            .filter(SalesEventModel.tenant_id == tenant_id)
            .order_by(SalesEventModel.created_at.desc())
            .all()
        )

    @staticmethod
    def list_products(db: Session, event_id: UUID) -> List[SalesEventProductModel]:
        return (
            db.query(SalesEventProductModel)
            .filter(SalesEventProductModel.event_id == event_id)
            .order_by(SalesEventProductModel.created_at.asc())
            .all()
        )

    @staticmethod
    def update(
        db: Session,
        event: SalesEventModel,
        name: str,
        start_date,
        end_date,
        products: List[dict],
    ) -> SalesEventModel:
        event.name = name
        event.start_date = start_date
        event.end_date = end_date

        db.query(SalesEventProductModel).filter(
            SalesEventProductModel.event_id == event.id
        ).delete(synchronize_session=False)

        for product in products:
            db.add(
                SalesEventProductModel(
                    event_id=event.id,
                    bling_product_id=product.get("bling_product_id"),
                    sku=(product.get("sku") or "").strip().upper(),
                    product_name=product.get("product_name"),
                )
            )

        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def delete(db: Session, event: SalesEventModel) -> None:
        db.query(SalesEventProductModel).filter(
            SalesEventProductModel.event_id == event.id
        ).delete(synchronize_session=False)
        db.delete(event)
        db.commit()
