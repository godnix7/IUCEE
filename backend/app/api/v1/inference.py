import os
import tempfile
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_roles, require_spatial_db
from app.core.config import settings
from app.models import ImageryAnalysis, Project, SpatialFeature, User, ProcessingJob
from app.schemas import AnalysisResponse
from app.services.storage_service import StorageService
from app.workers.tasks import process_imagery_analysis
from app.services.geo_service import GeoService, GeoServiceException

router = APIRouter()

_ALLOWED_MIME_TYPES = {
    ".tif": {"image/tiff", "image/x-tiff", "application/octet-stream"},
    ".tiff": {"image/tiff", "image/x-tiff", "application/octet-stream"},
    ".geotiff": {"image/tiff", "image/x-tiff", "application/octet-stream"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
}

_ALLOWED_MODES = {"segmentation", "detection", "scene_segmentation"}

@router.post("/upload")
def upload_imagery(
    project_id: int = Form(...),
    population_count: Optional[int] = Form(None),
    population_source: Optional[str] = Form(None),
    population_date: Optional[str] = Form(None),
    analysis_mode: str = Form("segmentation"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"])),
    _spatial: None = Depends(require_spatial_db)
):
    """Upload GeoTIFF / Drone Orthomosaic / Satellite image file for analysis.

    analysis_mode:
      - 'segmentation' (default): LoveDA land-cover segmentation. Best for nadir aerial/satellite.
      - 'detection': COCO object detection (vehicles/people). Best for oblique drone imagery.
    """
    analysis_mode = (analysis_mode or "segmentation").lower()
    if analysis_mode not in _ALLOWED_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid analysis_mode. Allowed: {sorted(_ALLOWED_MODES)}")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {settings.SUPPORTED_EXTENSIONS}"
        )

    declared_mime_type = (file.content_type or "").lower()
    allowed_mime_types = _ALLOWED_MIME_TYPES.get(ext, set())
    if declared_mime_type and declared_mime_type not in allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{declared_mime_type}' for '{ext}'. Allowed MIME types: {sorted(allowed_mime_types)}"
        )

    file_type = "geotiff" if ext in [".tif", ".tiff", ".geotiff"] else "satellite_png"
    
    # 1. Create a transaction for Analysis + Job
    analysis = ImageryAnalysis(
        project_id=project_id,
        filename=file.filename,
        file_path="pending", # placeholder
        file_type=file_type,
        analysis_mode=analysis_mode,
        population_count=population_count,
        population_source=population_source,
        population_date=population_date,
        status="pending"
    )
    db.add(analysis)
    db.flush() # get analysis.id

    # 2. Save file temporarily for CRS check
    fd, temp_file_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        total_bytes = 0
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        with open(temp_file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Maximum upload size is {settings.MAX_UPLOAD_SIZE_MB} MB."
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
        original_crs = None
        bounds = None
        width = None
        height = None
        resolution_x = None
        resolution_y = None
        footprint_wkt = None
        
        if file_type == "geotiff":
            meta = GeoService.read_raster_metadata(temp_file_path)
            original_crs = GeoService.validate_crs(meta["crs"])
            footprint_geom = GeoService.raster_bounds(temp_file_path)
            
            width = meta["width"]
            height = meta["height"]
            resolution_x = abs(meta["resolution"][0])
            resolution_y = abs(meta["resolution"][1])
            bounds = [
                footprint_geom.bounds[0],
                footprint_geom.bounds[1],
                footprint_geom.bounds[2],
                footprint_geom.bounds[3]
            ]
            footprint_wkt = footprint_geom.wkt
            
        analysis.original_crs = original_crs
        analysis.normalized_crs = "EPSG:4326" if original_crs else None
        analysis.bounds = bounds
        analysis.width = width
        analysis.height = height
        analysis.resolution_x = resolution_x
        analysis.resolution_y = resolution_y
        analysis.footprint = f"SRID=4326;{footprint_wkt}" if footprint_wkt else None

        # 3. Upload to authoritative MinIO
        safe_filename = file.filename.replace(" ", "_")
        object_key = f"analyses/{analysis.id}/source/{safe_filename}"
        StorageService.upload_file(temp_file_path, object_key)
        analysis.file_path = object_key
        
    except GeoServiceException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    # 4. Create ProcessingJob
    job = ProcessingJob(
        analysis_id=analysis.id,
        job_type="analysis",
        status="queued",
        current_stage="VALIDATING"
    )
    db.add(job)
    db.commit()
    db.refresh(analysis)
    db.refresh(job)
    
    # 5. Enqueue Celery Task
    task = process_imagery_analysis.delay(analysis.id, job.id)
    
    # Do not update DB with Celery task ID here, worker handles it to avoid race condition
    return {
        "analysis_id": analysis.id,
        "job_id": job.id,
        "status": "queued"
    }

@router.post("/{analysis_id}/run")
def run_ai_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"]))
):
    """Deprecated. Processing is now asynchronous via /upload"""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Synchronous processing is deprecated. Uploading automatically queues the job.")

@router.get("/{analysis_id}/status", response_model=AnalysisResponse)
def get_analysis_status(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time analysis status and results."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis

@router.get("/{analysis_id}/detection-overlay")
def get_detection_overlay(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stream the annotated detection overlay image (detection-mode analyses only)."""
    from fastapi.responses import StreamingResponse
    import io
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not analysis.detection_overlay_key:
        raise HTTPException(status_code=404, detail="No detection overlay for this analysis")

    fd, tmp = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        StorageService.download_file(analysis.detection_overlay_key, tmp)
        with open(tmp, "rb") as fh:
            data = fh.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return StreamingResponse(io.BytesIO(data), media_type="image/jpeg")
