from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
import glob
from pathlib import Path

from app.core.database import get_db
from app.models import Project, ProjectClass, Image
from app.schemas import Project as ProjectSchema, ProjectCreate
from app.core.config import settings

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
    # Verify folder path
    if not os.path.exists(project_in.root_path):
        raise HTTPException(status_code=400, detail="Root path does not exist")

    # Create project
    project = Project(
        name=project_in.name,
        description=project_in.description,
        root_path=project_in.root_path
    )
    db.add(project)
    db.flush()

    # Add classes from fixed ontology
    for cls in settings.DEFAULT_AERIAL_CLASSES:
        db.add(ProjectClass(
            project_id=project.id,
            name=cls["name"],
            color=cls["color"],
            shortcut_key=cls["shortcut_key"]
        ))

    # Auto Dataset Discovery
    root_dir = Path(project_in.root_path)
    extensions = settings.SUPPORTED_EXTENSIONS
    
    discovered_images = []
    
    # Recursively find all supported images
    for root, _, files in os.walk(root_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, root_dir)
                # Basic size info
                file_size = os.path.getsize(abs_path)
                
                # Use PIL for extremely fast header-only dimension extraction
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(abs_path) as img:
                        w, h = img.size
                except Exception:
                    w, h = 0, 0
                
                discovered_images.append(Image(
                    project_id=project.id,
                    filename=file,
                    relative_path=rel_path,
                    absolute_path=abs_path,
                    width=w,
                    height=h,
                    file_size_bytes=file_size,
                    status="pending",
                    review_status="accepted"
                ))
    
    if discovered_images:
        db.add_all(discovered_images)
        
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


@router.get("/{project_id}/images/{image_id}/file")
def get_image_file(project_id: int, image_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not os.path.exists(image.absolute_path):
        raise HTTPException(status_code=404, detail="Original file missing from disk")
    return FileResponse(image.absolute_path)

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
        from app.models import ProcessingQueue
        db.query(ProcessingQueue).filter(ProcessingQueue.status == "completed").delete()
        db.commit()
        return {"message": "Completed processing queue cleared."}
    elif req.target == "all":
        pass # All images
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
