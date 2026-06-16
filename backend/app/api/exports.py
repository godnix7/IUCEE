from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
import os

from app.core.database import get_db
from app.services.export_service import ExportService

router = APIRouter()

@router.post("/{project_id}/export")
def generate_export(project_id: int, mode: str = "reviewed", db: Session = Depends(get_db)):
    if mode not in ["reviewed", "human_corrected"]:
        raise HTTPException(status_code=400, detail="Invalid export mode")
        
    output_dir = os.path.join(os.getcwd(), "data", "exports")
    
    try:
        export_path = ExportService.export_dataset(db, project_id, output_dir, mode=mode)
        filename = os.path.basename(export_path)
        return {
            "message": "Export generated successfully", 
            "path": export_path, 
            "download_url": f"/api/v1/exports/{project_id}/download/{filename}"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{project_id}/download/{filename}")
def download_export(project_id: int, filename: str):
    export_path = os.path.join(os.getcwd(), "data", "exports", filename)
    if not os.path.exists(export_path):
        raise HTTPException(status_code=404, detail="Export file not found. Please generate it first.")
        
    return FileResponse(export_path, media_type="application/zip", filename=filename)

@router.get("/{project_id}/retraining-package")
def generate_retraining_package(project_id: int, db: Session = Depends(get_db)):
    from app.models import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    import shutil
    import time
    
    # Locate the active learning dataset
    dataset_dir = os.path.join(project.root_path, "corrections_dataset")
    if not os.path.exists(dataset_dir) or not os.listdir(dataset_dir):
        raise HTTPException(status_code=404, detail="No human corrections found yet. Please correct some labels in Label Studio first.")
        
    # Zip it
    export_dir = os.path.join(os.getcwd(), "data", "exports")
    os.makedirs(export_dir, exist_ok=True)
    
    zip_filename = f"retraining_package_{project.id}_{int(time.time())}"
    zip_path = os.path.join(export_dir, zip_filename)
    
    shutil.make_archive(zip_path, 'zip', dataset_dir)
    final_zip_path = zip_path + ".zip"
    
    return FileResponse(final_zip_path, media_type="application/zip", filename=f"{zip_filename}.zip")
