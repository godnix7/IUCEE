from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
from pathlib import Path

from fastapi.responses import FileResponse

from app.core.database import get_db
from app.models import Project, ProjectClass, Image, ProcessingQueue
from app.schemas import Project as ProjectSchema, ProjectCreate
from app.core.config import settings
from app.services.import_service import ImportService

router = APIRouter()

@router.get("/select-folder")
def select_folder():
    import tkinter as tk
    from tkinter import filedialog
    
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    folder_path = filedialog.askdirectory(parent=root, title="Select Dataset Folder")
    root.destroy()
    
    return {"path": folder_path}

@router.post("/", response_model=ProjectSchema)
def create_project(project_in: ProjectCreate, db: Session = Depends(get_db)):
    if not os.path.exists(project_in.root_path):
        raise HTTPException(status_code=400, detail="Root path does not exist")

    project = Project(
        name=project_in.name,
        description=project_in.description,
        root_path=project_in.root_path
    )
    db.add(project)
    db.flush()

    custom_classes = None
    if project_in.classes:
        custom_classes = [c.model_dump() for c in project_in.classes]

    import_stats = ImportService.index_project_folder(
        db, project, project_in.root_path, custom_classes=custom_classes
    )

    # Create processing queue entries for valid images (worker starts on demand)
    valid_images = db.query(Image).filter(
        Image.project_id == project.id,
        Image.is_corrupt == False,
        Image.is_duplicate == False,
        Image.status == "pending",
    ).all()
    for img in valid_images:
        db.add(ProcessingQueue(image_id=img.id))
    db.commit()

    db.refresh(project)
    project.description = (
        f"{project_in.description or ''} | Import: {import_stats['valid']} valid, "
        f"{import_stats['duplicates']} duplicates, {import_stats['corrupt']} corrupt"
    ).strip(" |")
    db.commit()
    db.refresh(project)
    return project

@router.get("/", response_model=List[ProjectSchema])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Project).offset(skip).limit(limit).all()

@router.get("/{project_id}", response_model=ProjectSchema)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}/import-stats")
def get_import_stats(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    total = db.query(Image).filter(Image.project_id == project_id).count()
    corrupt = db.query(Image).filter(Image.project_id == project_id, Image.is_corrupt == True).count()
    duplicates = db.query(Image).filter(Image.project_id == project_id, Image.is_duplicate == True).count()
    valid = total - corrupt

    return {
        "total": total,
        "valid": valid - duplicates,
        "duplicates": duplicates,
        "corrupt": corrupt,
    }

@router.get("/{project_id}/images/{image_id}/file")
def get_image_file(project_id: int, image_id: int, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not os.path.exists(image.absolute_path):
        raise HTTPException(status_code=404, detail="Original file missing from disk")
    return FileResponse(image.absolute_path)

@router.get("/{project_id}/images/{image_id}/thumbnail")
def get_image_thumbnail(project_id: int, image_id: int, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image or not image.thumbnail_path or not os.path.exists(image.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(image.thumbnail_path)

@router.get("/{project_id}/images/{image_id}/mask-overlay")
def get_mask_overlay(project_id: int, image_id: int, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image or not image.mask_path or not os.path.exists(image.mask_path):
        raise HTTPException(status_code=404, detail="Mask overlay not found")
    return FileResponse(image.mask_path)

from pydantic import BaseModel
class CleanupRequest(BaseModel):
    target: str
    delete_source_files: bool = False

@router.post("/{project_id}/cleanup")
def cleanup_project(project_id: int, req: CleanupRequest, db: Session = Depends(get_db)):
    query = db.query(Image).filter(Image.project_id == project_id)
    
    if req.target == "processed":
        query = query.filter(Image.status == "completed")
    elif req.target == "reviewed":
        query = query.filter(Image.review_status.in_(["reviewed", "human_corrected"]))
    elif req.target == "accepted":
        query = query.filter(Image.review_status == "accepted")
    elif req.target == "rejected":
        query = query.filter(Image.review_status == "rejected")
    elif req.target == "completed_queue":
        db.query(ProcessingQueue).filter(ProcessingQueue.status == "completed").delete()
        db.commit()
        return {"message": "Completed processing queue cleared."}
    elif req.target == "all":
        pass
    else:
        raise HTTPException(status_code=400, detail="Invalid cleanup target")
        
    images_to_delete = query.all()
    count = len(images_to_delete)
    
    for img in images_to_delete:
        if req.delete_source_files and os.path.exists(img.absolute_path):
            try:
                os.remove(img.absolute_path)
            except Exception as e:
                print(f"Failed to delete file {img.absolute_path}: {e}")
        db.delete(img)
        
    db.commit()
    return {"message": f"Deleted {count} images"}
