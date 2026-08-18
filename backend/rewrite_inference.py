import re

with open('app/api/v1/inference.py', 'r') as f:
    content = f.read()

# We want to replace the upload_imagery and run_ai_analysis functions.
# Let's just create a new file based on the old one.
new_content = """import os
import shutil
import tempfile
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_roles, require_spatial_db
from app.core.config import settings
from app.models import ImageryAnalysis, Project, SpatialFeature, UrbanBenchmark, User, ProcessingJob
from app.schemas import AnalysisResponse
from app.services.storage_service import StorageService
from app.workers.tasks import process_imagery_analysis
from app.services.geo_service import GeoService, GeoServiceException

router = APIRouter()

@router.post("/upload")
def upload_imagery(
    project_id: int = Form(...),
    population_estimate: Optional[int] = Form(1000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"])),
    _spatial: None = Depends(require_spatial_db)
):
    \"\"\"Upload GeoTIFF / Drone Orthomosaic / Satellite image file for analysis.\"\"\"
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {settings.SUPPORTED_EXTENSIONS}"
        )

    file_type = "geotiff" if ext in [".tif", ".tiff", ".geotiff"] else "satellite_png"
    
    # 1. Create a transaction for Analysis + Job
    analysis = ImageryAnalysis(
        project_id=project_id,
        filename=file.filename,
        file_path="pending", # placeholder
        file_type=file_type,
        population_estimate=population_estimate or 1000,
        status="pending"
    )
    db.add(analysis)
    db.flush() # get analysis.id

    # 2. Save file temporarily for CRS check
    fd, temp_file_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
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
    \"\"\"Deprecated. Processing is now asynchronous via /upload\"\"\"
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Synchronous processing is deprecated. Uploading automatically queues the job.")

@router.get("/{analysis_id}/status", response_model=AnalysisResponse)
def get_analysis_status(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    \"\"\"Get real-time analysis status and results.\"\"\"
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
"""

with open('app/api/v1/inference.py', 'w') as f:
    f.write(new_content)
