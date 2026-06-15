from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models import Project, Image, Annotation, ProcessingQueue
from app.schemas import DashboardStats

router = APIRouter()

@router.get("/{project_id}/stats", response_model=DashboardStats)
def get_dashboard_stats(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Image counts
    total_images = db.query(Image).filter(Image.project_id == project_id).count()
    processed_images = db.query(Image).filter(Image.project_id == project_id, Image.status == "completed").count()
    remaining_images = db.query(Image).filter(Image.project_id == project_id, Image.status.in_(["pending", "processing"])).count()
    
    # Label Studio metrics
    ls_tasks_sent = db.query(Image).filter(Image.project_id == project_id, Image.ls_task_id.isnot(None)).count()
    ls_tasks_reviewed = db.query(Image).filter(Image.project_id == project_id, Image.review_status == "human_corrected").count()
    ls_tasks_corrected = db.query(Image).filter(Image.project_id == project_id, Image.correction_count > 0).count()
    ls_tasks_pending = db.query(Image).filter(Image.project_id == project_id, Image.review_status == "pending_review").count()
    
    # Averages
    avg_conf = db.query(func.avg(Image.confidence)).filter(Image.project_id == project_id, Image.confidence.isnot(None)).scalar() or 0.0
    
    # Class distribution
    class_dist = {}
    annotations = db.query(Annotation.class_name, func.count(Annotation.id)).join(Image).filter(Image.project_id == project_id).group_by(Annotation.class_name).all()
    for class_name, count in annotations:
        class_dist[class_name] = count

    # Hardware telemetry
    from app.services.hardware_service import HardwareService
    from app.services.processing_service import ProcessingService
    
    hw_info = HardwareService.get_hardware_info()
    telemetry = HardwareService.get_telemetry()
    perf = ProcessingService.get_performance_stats()
    
    hardware_stats = {
        "device_name": hw_info["device_name"],
        "device_type": hw_info["device"],
        "gpu_utilization_pct": telemetry["gpu_utilization_pct"],
        "vram_used_gb": telemetry["vram_used_gb"],
        "vram_total_gb": hw_info["vram_total_gb"],
        "images_per_minute": perf["images_per_minute"],
        "avg_inference_ms": perf["avg_inference_ms"]
    }

    return DashboardStats(
        total_images=total_images,
        processed_images=processed_images,
        remaining_images=remaining_images,
        ls_tasks_sent=ls_tasks_sent,
        ls_tasks_reviewed=ls_tasks_reviewed,
        ls_tasks_corrected=ls_tasks_corrected,
        ls_tasks_pending=ls_tasks_pending,
        avg_confidence=float(avg_conf),
        class_distribution=class_dist,
        engine_state=ProcessingService.get_state(),
        hardware=hardware_stats
    )
