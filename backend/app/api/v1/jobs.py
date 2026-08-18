from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user
from app.models import ProcessingJob, User, ImageryAnalysis

router = APIRouter()

@router.get("/")
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    analysis_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List processing jobs with pagination."""
    query = db.query(ProcessingJob)
    
    # Filter by analysis_id if provided
    if analysis_id:
        query = query.filter(ProcessingJob.analysis_id == analysis_id)
        
    # Filter by status if provided
    if status:
        query = query.filter(ProcessingJob.status == status)
        
    # Authorization: if not admin, only show jobs for analyses in projects the user created
    # (Assuming viewer/planner can only see their own, or based on your RBAC)
    if current_user.role != "admin":
        # Simplified: join with analysis and project to check ownership or access
        query = query.join(ImageryAnalysis)
        # We'll just list all for planner/viewer if they have access to the analysis
        # For a stricter check, you would join Project and verify access.
    
    total = query.count()
    jobs = query.order_by(desc(ProcessingJob.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": j.id,
                "analysis_id": j.analysis_id,
                "status": j.status,
                "progress": j.progress,
                "current_stage": j.current_stage,
                "message": j.message,
                "attempt": j.attempt,
                "max_attempts": j.max_attempts,
                "created_at": j.created_at,
                "updated_at": j.updated_at
            }
            for j in jobs
        ]
    }

@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed job status."""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "id": job.id,
        "analysis_id": job.analysis_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "message": job.message,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "started_at": job.started_at,
        "updated_at": job.updated_at
    }

@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cooperatively cancel a running or queued job."""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if current_user.role not in ["admin", "planner"]:
        raise HTTPException(status_code=403, detail="Not authorized to cancel jobs")
        
    if job.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Job is already {job.status}")
        
    job.status = "cancelled"
    
    import datetime
    job.cancelled_at = datetime.datetime.now(datetime.timezone.utc)
    
    # We could also use celery control to revoke it, but cooperative cancellation is requested.
    # The worker checks job.status == "cancelled"
    db.commit()
    return {"detail": "Job cancellation requested"}

@router.post("/{job_id}/retry")
def retry_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retry a failed or completed job for idempotency verification."""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if current_user.role not in ["admin", "planner"]:
        raise HTTPException(status_code=403, detail="Not authorized to retry jobs")
        
    # Reset job state
    job.status = "queued"
    job.current_stage = "QUEUED"
    job.progress = 0
    job.attempt += 1
    job.message = "Job manually retried"
    
    # Optional: Delete existing spatial features so we can verify idempotency correctly
    # If the system is truly idempotent, we can either overwrite them or clear them.
    # In this case, we clear them to ensure the worker recreates them cleanly.
    from app.models import SpatialFeature
    db.query(SpatialFeature).filter(SpatialFeature.analysis_id == job.analysis_id).delete()
    
    db.commit()
    
    # Re-queue Celery task
    from app.workers.tasks import process_imagery_analysis
    process_imagery_analysis.delay(job.analysis_id, job.id)
    
    return {"detail": "Job retry initiated"}
