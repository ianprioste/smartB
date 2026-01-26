"""Repository for Jobs."""
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from app.models.database import JobModel, JobItemModel, JobStatusEnum, JobItemStatusEnum
from app.infra.logging import get_logger

logger = get_logger(__name__)


class JobRepository:
    """Repository for managing jobs."""

    @staticmethod
    def create(
        db: Session,
        tenant_id: UUID,
        job_type: str,
        input_payload: dict = None,
        metadata: dict = None,
    ) -> JobModel:
        """Create a new job."""
        
        job = JobModel(
            tenant_id=tenant_id,
            type=job_type,
            status=JobStatusEnum.DRAFT,
            input_payload=input_payload or {},
            job_metadata=metadata or {},
        )
        db.add(job)
        db.commit()

        logger.info(
            "job_created job_id=%s job_type=%s tenant_id=%s",
            str(job.id),
            job_type,
            str(tenant_id),
        )

        return job

    @staticmethod
    def get_by_id(db: Session, job_id: UUID) -> Optional[JobModel]:
        """Get job by ID."""
        return db.query(JobModel).filter(JobModel.id == job_id).first()

    @staticmethod
    def update_status(
        db: Session,
        job_id: UUID,
        status: JobStatusEnum,
        started_at: datetime = None,
        finished_at: datetime = None,
    ) -> JobModel:
        """Update job status."""
        
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = status
        
        if started_at:
            job.started_at = started_at
        if finished_at:
            job.finished_at = finished_at

        db.add(job)
        db.commit()

        logger.info(
            "job_status_updated job_id=%s status=%s",
            str(job_id),
            status.value,
        )

        return job

    @staticmethod
    def get_queued_jobs(db: Session, limit: int = 10) -> List[JobModel]:
        """Get queued jobs for processing."""
        return db.query(JobModel).filter(
            JobModel.status == JobStatusEnum.QUEUED
        ).limit(limit).all()

    @staticmethod
    def list_jobs(db: Session, limit: int = 50) -> List[JobModel]:
        """List recent jobs (default limit 50)."""
        return db.query(JobModel).order_by(JobModel.created_at.desc()).limit(limit).all()

    @staticmethod
    def delete_all(db: Session) -> int:
        """Delete all jobs and items (cleanup)."""
        deleted_items = db.query(JobItemModel).delete()
        deleted_jobs = db.query(JobModel).delete()
        db.commit()

        logger.info(
            "jobs_cleared deleted_jobs=%s deleted_items=%s",
            deleted_jobs,
            deleted_items,
        )

        return deleted_jobs


class JobItemRepository:
    """Repository for managing job items."""

    @staticmethod
    def create(
        db: Session,
        job_id: UUID,
        payload: dict = None,
    ) -> JobItemModel:
        """Create a new job item."""
        
        item = JobItemModel(
            job_id=job_id,
            status=JobItemStatusEnum.PENDING,
            payload=payload or {},
        )
        db.add(item)
        db.commit()

        logger.info(
            "job_item_created job_item_id=%s job_id=%s",
            str(item.id),
            str(job_id),
        )

        return item

    @staticmethod
    def get_by_job_id(db: Session, job_id: UUID) -> List[JobItemModel]:
        """Get all items for a job."""
        return db.query(JobItemModel).filter(
            JobItemModel.job_id == job_id
        ).all()

    @staticmethod
    def update_status(
        db: Session,
        item_id: UUID,
        status: JobItemStatusEnum,
        result: dict = None,
        error_message: str = None,
        started_at: datetime = None,
        finished_at: datetime = None,
    ) -> JobItemModel:
        """Update job item status."""
        
        item = db.query(JobItemModel).filter(JobItemModel.id == item_id).first()
        
        if not item:
            raise ValueError(f"Job item {item_id} not found")

        item.status = status
        
        if result:
            item.result = result
        if error_message:
            item.error_message = error_message
        if started_at:
            item.started_at = started_at
        if finished_at:
            item.finished_at = finished_at

        db.add(item)
        db.commit()

        logger.info(
            "job_item_status_updated job_item_id=%s status=%s",
            str(item_id),
            status.value,
        )

        return item

    @staticmethod
    def get_pending_items(db: Session, job_id: UUID) -> List[JobItemModel]:
        """Get pending items for a job."""
        return db.query(JobItemModel).filter(
            JobItemModel.job_id == job_id,
            JobItemModel.status == JobItemStatusEnum.PENDING,
        ).all()
