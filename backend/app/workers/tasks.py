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
from app.models.database import JobStatusEnum, JobItemStatusEnum
from app.repositories.job_repo import JobRepository, JobItemRepository

logger = get_logger(__name__)

# Create a separate engine for Celery worker
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
