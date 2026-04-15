"""Worker tasks for async job processing."""
import asyncio
import time
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.workers.celery_app import celery_app
from app.settings import settings
from app.infra.logging import get_logger
from app.infra.bling_client import BlingClient
from app.models.database import JobStatusEnum, JobItemStatusEnum
from app.repositories.job_repo import JobRepository, JobItemRepository
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.order_snapshot_repo import OrderSnapshotRepository
from app.domain.order_sync import sync_orders, sync_single_order
from app.domain.product_sync import sync_single_product

logger = get_logger(__name__)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Create a separate engine for Celery worker
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _make_bling_client(db: Session):
    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        return None

    def _save(access_token, refresh_token, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

    return BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )


@celery_app.task(bind=True, name="process_job")
def process_job_task(self, job_id: str):
    """
    Process a job.
    
    This is a minimal implementation for Sprint 1 to prove:
    - Job consumption from queue
    - Status updates
    - Worker → DB communication
    """
    
    job_id = UUID(job_id)
    db = SessionLocal()
    
    try:
        logger.info(
            "job_processing_started task_id=%s job_id=%s",
            self.request.id,
            str(job_id),
        )
        
        # Get job
        job = JobRepository.get_by_id(db, job_id)
        
        if not job:
            logger.error(
                "job_not_found_in_worker task_id=%s job_id=%s",
                self.request.id,
                str(job_id),
            )
            return {"error": "Job not found"}
        
        # Update job status to RUNNING
        JobRepository.update_status(
            db=db,
            job_id=job_id,
            status=JobStatusEnum.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        # Create a sample job item (for demonstration)
        item = JobItemRepository.create(
            db=db,
            job_id=job_id,
            payload={"processing": True},
        )
        
        logger.info(
            "job_item_created_by_worker task_id=%s job_id=%s item_id=%s",
            self.request.id,
            str(job_id),
            str(item.id),
        )
        
        # Update item status to RUNNING
        JobItemRepository.update_status(
            db=db,
            item_id=item.id,
            status=JobItemStatusEnum.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        # Simulate work (minimal for Sprint 1)
        logger.info(
            "job_processing_work task_id=%s job_id=%s message=%s",
            self.request.id,
            str(job_id),
            "Simulating work for 2 seconds",
        )
        
        time.sleep(2)  # Simulate some processing
        
        # Update item status to OK
        JobItemRepository.update_status(
            db=db,
            item_id=item.id,
            status=JobItemStatusEnum.OK,
            result={"processed": True, "timestamp": datetime.utcnow().isoformat()},
            finished_at=datetime.utcnow(),
        )
        
        # Update job status to DONE
        JobRepository.update_status(
            db=db,
            job_id=job_id,
            status=JobStatusEnum.DONE,
            finished_at=datetime.utcnow(),
        )
        
        logger.info(
            "job_processing_completed task_id=%s job_id=%s",
            self.request.id,
            str(job_id),
        )
        
        return {
            "job_id": str(job_id),
            "status": "completed",
        }
    
    except Exception as e:
        logger.error(
            "job_processing_error task_id=%s job_id=%s error=%s",
            self.request.id,
            str(job_id),
            str(e),
        )
        
        # Update job to FAILED
        try:
            JobRepository.update_status(
                db=db,
                job_id=job_id,
                status=JobStatusEnum.FAILED,
                finished_at=datetime.utcnow(),
            )
        except Exception as update_error:
            logger.error(
                "failed_to_update_job_status_after_error task_id=%s job_id=%s error=%s",
                self.request.id,
                str(job_id),
                str(update_error),
            )
        
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True, name="sync_orders_full_task")
def sync_orders_full_task(self):
    """On-demand task: full sync from Bling to local order snapshot DB."""
    db = SessionLocal()
    client = None
    try:
        client = _make_bling_client(db)
        if not client:
            logger.warning("orders_full_sync_skipped reason=no_bling_token")
            OrderSnapshotRepository.mark_sync_failure(
                db,
                DEFAULT_TENANT_ID,
                "sync full: Bling não autenticado",
            )
            db.commit()
            return {"ok": False, "reason": "no_bling_token"}

        result = asyncio.run(sync_orders(db, DEFAULT_TENANT_ID, client, mode="full"))
        logger.info(
            "orders_full_sync_done listed=%s upserted=%s failed=%s",
            result.get("total_listed"),
            result.get("upserted"),
            result.get("failed"),
        )
        return {"ok": True, **result}
    except Exception as exc:
        logger.error("orders_full_sync_failed error=%s", str(exc), exc_info=True)
        OrderSnapshotRepository.mark_sync_failure(
            db,
            DEFAULT_TENANT_ID,
            f"sync full failed: {exc}",
        )
        db.commit()
        return {"ok": False, "error": str(exc)}
    finally:
        if client is not None:
            try:
                asyncio.run(client.client.aclose())
            except Exception:
                pass
        db.close()


@celery_app.task(bind=True, name="sync_orders_incremental_task")
def sync_orders_incremental_task(self):
    """Periodic task: incremental sync from Bling to local order snapshot DB."""
    db = SessionLocal()
    client = None
    try:
        client = _make_bling_client(db)
        if not client:
            logger.warning("orders_incremental_sync_skipped reason=no_bling_token")
            OrderSnapshotRepository.mark_sync_failure(
                db,
                DEFAULT_TENANT_ID,
                "sync incremental: Bling não autenticado",
            )
            db.commit()
            return {"ok": False, "reason": "no_bling_token"}

        result = asyncio.run(sync_orders(db, DEFAULT_TENANT_ID, client, mode="incremental"))
        logger.info(
            "orders_incremental_sync_done listed=%s upserted=%s failed=%s",
            result.get("total_listed"),
            result.get("upserted"),
            result.get("failed"),
        )
        return {"ok": True, **result}
    except Exception as exc:
        logger.error("orders_incremental_sync_failed error=%s", str(exc), exc_info=True)
        OrderSnapshotRepository.mark_sync_failure(
            db,
            DEFAULT_TENANT_ID,
            f"sync incremental failed: {exc}",
        )
        db.commit()
        return {"ok": False, "error": str(exc)}
    finally:
        if client is not None:
            try:
                asyncio.run(client.client.aclose())
            except Exception:
                pass
        db.close()


@celery_app.task(bind=True, name="process_webhook_order_task", max_retries=5)
def process_webhook_order_task(self, event_id: str, bling_order_id: int):
    """Process a Bling webhook order event: fetch detail and upsert snapshot."""
    from app.repositories.webhook_repo import WebhookEventRepository

    event_uuid = UUID(event_id)
    db = SessionLocal()
    client = None
    try:
        WebhookEventRepository.set_processing(db, event_uuid)

        client = _make_bling_client(db)
        if not client:
            raise RuntimeError("Bling nao autenticado - token ausente")

        result = asyncio.run(
            sync_single_order(db, DEFAULT_TENANT_ID, client, bling_order_id)
        )

        if not result.get("ok"):
            raise RuntimeError(result.get("error", "sync_single_order returned not ok"))

        WebhookEventRepository.mark_processed(db, event_uuid)
        logger.info(
            "webhook_order_processed event_id=%s bling_order_id=%s",
            event_id,
            bling_order_id,
        )
        return {"ok": True, "bling_order_id": bling_order_id}

    except Exception as exc:
        error_str = str(exc)
        logger.warning(
            "webhook_order_processing_failed event_id=%s bling_order_id=%s attempt=%s error=%s",
            event_id,
            bling_order_id,
            self.request.retries + 1,
            error_str,
        )
        WebhookEventRepository.mark_failed(
            db, event_uuid, error_str, max_retries=settings.WEBHOOK_MAX_RETRIES
        )
        delay = settings.WEBHOOK_RETRY_BASE_DELAY_S * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=delay, max_retries=settings.WEBHOOK_MAX_RETRIES)

    finally:
        if client is not None:
            try:
                asyncio.run(client.client.aclose())
            except Exception:
                pass
        db.close()


@celery_app.task(bind=True, name="process_webhook_product_task", max_retries=5)
def process_webhook_product_task(self, event_id: str, bling_product_id: int, event_kind: str = "product"):
    """Process product/stock webhook events and upsert product snapshot."""
    from app.repositories.webhook_repo import WebhookEventRepository

    event_uuid = UUID(event_id)
    db = SessionLocal()
    client = None
    try:
        WebhookEventRepository.set_processing(db, event_uuid)

        client = _make_bling_client(db)
        if not client:
            raise RuntimeError("Bling nao autenticado - token ausente")

        result = asyncio.run(sync_single_product(db, DEFAULT_TENANT_ID, client, bling_product_id))

        if not result.get("ok"):
            raise RuntimeError(result.get("error", "sync_single_product returned not ok"))

        WebhookEventRepository.mark_processed(db, event_uuid)
        logger.info(
            "webhook_%s_processed event_id=%s bling_product_id=%s",
            event_kind,
            event_id,
            bling_product_id,
        )
        return {"ok": True, "bling_product_id": bling_product_id, "event_kind": event_kind}

    except Exception as exc:
        error_str = str(exc)
        logger.warning(
            "webhook_%s_processing_failed event_id=%s bling_product_id=%s attempt=%s error=%s",
            event_kind,
            event_id,
            bling_product_id,
            self.request.retries + 1,
            error_str,
        )
        WebhookEventRepository.mark_failed(
            db, event_uuid, error_str, max_retries=settings.WEBHOOK_MAX_RETRIES
        )
        delay = settings.WEBHOOK_RETRY_BASE_DELAY_S * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=delay, max_retries=settings.WEBHOOK_MAX_RETRIES)

    finally:
        if client is not None:
            try:
                asyncio.run(client.client.aclose())
            except Exception:
                pass
        db.close()
