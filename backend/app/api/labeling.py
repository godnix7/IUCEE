from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
from datetime import datetime

from app.core.database import get_db
from app.models import Project, ProcessingQueue, Image
from app.schemas import QueueStatus
from app.services.processing_service import ProcessingService

router = APIRouter()

from pydantic import BaseModel
from typing import Optional

class AutoLabelRequest(BaseModel):
    model_name: Optional[str] = "wu-pr-gw/segformer-b2-finetuned-with-LoveDA"

@router.post("/{project_id}/auto-label")
def start_auto_labeling(project_id: int, request: Optional[AutoLabelRequest] = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    model_name = request.model_name if request else "wu-pr-gw/segformer-b2-finetuned-with-LoveDA"
    count = ProcessingService.enqueue_all(db, project_id, model_name)
    return {"message": f"Enqueued {count} images for background processing with {model_name}", "state": "RUNNING"}

@router.post("/{project_id}/pause")
def pause_auto_labeling(project_id: int):
    ProcessingService().pause_worker()
    return {"message": "Processing paused", "state": "PAUSED"}

@router.post("/{project_id}/resume")
def resume_auto_labeling(project_id: int):
    ProcessingService().resume_worker()
    return {"message": "Processing resumed", "state": "RUNNING"}

@router.post("/{project_id}/stop")
def stop_auto_labeling(project_id: int):
    ProcessingService().stop_worker()
    return {"message": "Processing stopped", "state": "STOPPED"}

@router.get("/{project_id}/queue-status")
def get_queue_status(project_id: int, db: Session = Depends(get_db)):
    # Calculate queue statistics
    pending = db.query(ProcessingQueue).join(Image).filter(Image.project_id == project_id, ProcessingQueue.status == "pending").count()
    processing = db.query(ProcessingQueue).join(Image).filter(Image.project_id == project_id, ProcessingQueue.status == "processing").count()
    completed = db.query(ProcessingQueue).join(Image).filter(Image.project_id == project_id, ProcessingQueue.status == "completed").count()
    failed = db.query(ProcessingQueue).join(Image).filter(Image.project_id == project_id, ProcessingQueue.status == "failed").count()
    
    stats = ProcessingService.get_performance_stats()
    processing_speed_ips = stats["images_per_minute"] / 60.0
    eta_seconds = int(pending / processing_speed_ips) if processing_speed_ips > 0 else 0

    return {
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "processing_speed_ips": processing_speed_ips,
        "eta_seconds": eta_seconds,
        "engine_state": ProcessingService.get_state()
    }
