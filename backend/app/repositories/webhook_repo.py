"""Repository for Bling webhook event log (idempotency + retry tracking)."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database import BlingWebhookEventModel, BlingWebhookEventStatusEnum
from app.infra.logging import get_logger

logger = get_logger(__name__)


class WebhookEventRepository:

    @staticmethod
    def create_if_new(
        db: Session,
        tenant_id: UUID,
        idempotency_key: str,
        event_type: str,
        bling_order_id: Optional[int],
        raw_payload: Optional[Dict[str, Any]],
    ) -> Optional[BlingWebhookEventModel]:
        """Insert a new event row.  Returns None (without error) if duplicate."""
        row = BlingWebhookEventModel(
            id=_uuid.uuid4(),
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            event_type=event_type,
            bling_order_id=bling_order_id,
            raw_payload=raw_payload,
            status=BlingWebhookEventStatusEnum.received,
            attempts=0,
            received_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        try:
            db.flush()
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
            logger.info("webhook_event_duplicate idempotency_key=%s", idempotency_key)
            return None

    @staticmethod
    def set_processing(db: Session, event_id: UUID) -> None:
        row = db.query(BlingWebhookEventModel).filter(BlingWebhookEventModel.id == event_id).first()
        if row:
            row.status = BlingWebhookEventStatusEnum.processing
            row.attempts = (row.attempts or 0) + 1
            row.updated_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def mark_processed(db: Session, event_id: UUID) -> None:
        row = db.query(BlingWebhookEventModel).filter(BlingWebhookEventModel.id == event_id).first()
        if row:
            row.status = BlingWebhookEventStatusEnum.processed
            row.processed_at = datetime.utcnow()
            row.updated_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def mark_failed(db: Session, event_id: UUID, error: str, max_retries: int = 5) -> None:
        row = db.query(BlingWebhookEventModel).filter(BlingWebhookEventModel.id == event_id).first()
        if row:
            row.last_error = error[:1000]
            row.updated_at = datetime.utcnow()
            if (row.attempts or 0) >= max_retries:
                row.status = BlingWebhookEventStatusEnum.dead
            else:
                row.status = BlingWebhookEventStatusEnum.failed
            db.commit()

    @staticmethod
    def list_pending_retry(db: Session, tenant_id: UUID, limit: int = 50) -> List[BlingWebhookEventModel]:
        """Return failed events that still have retry budget, ordered oldest first."""
        return (
            db.query(BlingWebhookEventModel)
            .filter(
                BlingWebhookEventModel.tenant_id == tenant_id,
                BlingWebhookEventModel.status == BlingWebhookEventStatusEnum.failed,
            )
            .order_by(BlingWebhookEventModel.received_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def health_summary(db: Session, tenant_id: UUID) -> Dict[str, Any]:
        from sqlalchemy import func as _func
        rows = (
            db.query(
                BlingWebhookEventModel.status,
                _func.count(BlingWebhookEventModel.id).label("cnt"),
            )
            .filter(BlingWebhookEventModel.tenant_id == tenant_id)
            .group_by(BlingWebhookEventModel.status)
            .all()
        )
        counts = {r.status.value: r.cnt for r in rows}
        last = (
            db.query(BlingWebhookEventModel)
            .filter(
                BlingWebhookEventModel.tenant_id == tenant_id,
                BlingWebhookEventModel.status == BlingWebhookEventStatusEnum.processed,
            )
            .order_by(BlingWebhookEventModel.processed_at.desc())
            .first()
        )
        return {
            "counts": counts,
            "last_processed_at": last.processed_at.isoformat() if last and last.processed_at else None,
        }
