"""Repository helpers for sales events."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.database import SalesEventModel, SalesEventProductModel


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
