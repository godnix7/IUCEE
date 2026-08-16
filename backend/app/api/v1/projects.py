from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_roles
from app.models import Project, User, ImageryAnalysis
from app.schemas import ProjectCreate, ProjectResponse

router = APIRouter()

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available projects with analysis count."""
    projects = db.query(Project).all()
    result = []
    for proj in projects:
        count = db.query(ImageryAnalysis).filter(ImageryAnalysis.project_id == proj.id).count()
        proj_dict = ProjectResponse.from_orm(proj)
        proj_dict.analysis_count = count
        result.append(proj_dict)
    return result

@router.post("", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"]))
):
    """Create a new project (Admin or Planner role required)."""
    project = Project(
        name=project_in.name,
        description=project_in.description,
        created_by_id=current_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    res = ProjectResponse.from_orm(project)
    res.analysis_count = 0
    return res

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project details by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    count = db.query(ImageryAnalysis).filter(ImageryAnalysis.project_id == project.id).count()
    res = ProjectResponse.from_orm(project)
    res.analysis_count = count
    return res

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """Delete a project (Admin only)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None
