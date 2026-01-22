"""Job management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from app.infra.db import get_db
from app.infra.logging import get_logger
from app.models.schemas import (
    JobCreateRequest,
    JobResponse,
    JobDetailResponse,
    JobItemResponse,
)
from app.models.database import JobStatusEnum
from app.repositories.job_repo import JobRepository, JobItemRepository
from app.repositories.bling_token_repo import BlingTokenRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Fixed tenant ID for Sprint 1 (single-tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    db: Session = Depends(get_db),
):
    """
    List recent jobs (ordered by creation time, max 50).
    
    **Returns:** Array of jobs with status, timestamps, and payloads.
    Useful for monitoring job queue and completion.
    """
    jobs = JobRepository.list_jobs(db)
    return [JobResponse.from_orm(job) for job in jobs]


@router.delete("", status_code=204)
async def delete_all_jobs(
    db: Session = Depends(get_db),
):
    """
    Delete all jobs and items (cleanup only).
    
    ⚠️ **Caution:** This is destructive. Use for development/testing only.
    Returns 204 No Content on success.
    """
    JobRepository.delete_all(db)
    return None


@router.post("", response_model=JobResponse)
async def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new async job.
    
    Jobs start in QUEUED status and are processed by workers asynchronously.
    Use polling on `GET /jobs/{id}` to monitor status.
    
    **Request Body:**
    - `type`: Job type identifier (e.g., "sync_products", "sync_orders")
    - `input_payload`: Job-specific input data (optional)
    - `metadata`: Custom metadata (optional)
    
    **Status Lifecycle:** DRAFT → QUEUED → RUNNING → DONE (or FAILED)
    
    **Example:**
    ```json
    {
      "type": "sync_products",
      "input_payload": {"resource": "products"},
      "metadata": {"source": "api"}
    }
    ```
    """
    
    request_id = str(uuid.uuid4())
    
    logger.info(
        "job_create_request",
        job_type=request.type,
    )
    
    try:
        job = JobRepository.create(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            job_type=request.type,
            input_payload=request.input_payload,
            metadata=request.metadata,
        )
        
        # Change status to QUEUED
        job = JobRepository.update_status(
            db=db,
            job_id=job.id,
            status=JobStatusEnum.QUEUED,
        )
        
        logger.info(
            "job_created_and_queued",
            job_id=str(job.id),
            job_type=request.type,
        )
        
        return JobResponse.from_orm(job)
    
    except Exception as e:
        logger.error(
            "job_create_error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to create job")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get job status and basic info.
    
    Use this to poll job completion. Includes timestamps and payload.
    For detailed items, use `GET /jobs/{id}/detail` instead.
    """
    
    request_id = str(uuid.uuid4())
    
    job = JobRepository.get_by_id(db, job_id)
    
    if not job:
        logger.warn(
            "job_not_found",
            request_id=request_id,
            job_id=str(job_id),
        )
        raise HTTPException(status_code=404, detail="Job not found")
    
    logger.info(
        "job_retrieved",
        job_id=str(job_id),
        status=job.status.value,
    )
    
    return JobResponse.from_orm(job)


@router.get("/{job_id}/detail", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """Get job with all items."""
    
    request_id = str(uuid.uuid4())
    
    job = JobRepository.get_by_id(db, job_id)
    
    if not job:
        logger.warn(
            "job_not_found",
            request_id=request_id,
            job_id=str(job_id),
        )
        raise HTTPException(status_code=404, detail="Job not found")
    
    items = JobItemRepository.get_by_job_id(db, job_id)
    
    logger.info(
        "job_detail_retrieved",
        request_id=request_id,
        job_id=str(job_id),
        items_count=len(items),
    )
    
    job_dict = JobResponse.from_orm(job).dict()
    return JobDetailResponse(
        **job_dict,
        items=[JobItemResponse.from_orm(item) for item in items],
    )


@router.get("/{job_id}/items", response_model=list[JobItemResponse])
async def get_job_items(
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all items for a job."""
    
    request_id = str(uuid.uuid4())
    
    # Verify job exists
    job = JobRepository.get_by_id(db, job_id)
    
    if not job:
        logger.warn(
            "job_not_found",
            request_id=request_id,
            job_id=str(job_id),
        )
        raise HTTPException(status_code=404, detail="Job not found")
    
    items = JobItemRepository.get_by_job_id(db, job_id)
    
    logger.info(
        "job_items_retrieved",
        request_id=request_id,
        job_id=str(job_id),
        items_count=len(items),
    )
    
    return [JobItemResponse.from_orm(item) for item in items]
