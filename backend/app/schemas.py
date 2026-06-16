from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ProjectClassBase(BaseModel):
    name: str
    color: str
    shortcut_key: Optional[str] = None

class ProjectClassCreate(ProjectClassBase):
    pass

class ProjectClass(ProjectClassBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    root_path: str

class ProjectCreate(ProjectBase):
    classes: List[ProjectClassCreate] = []

class Project(ProjectBase):
    id: int
    created_at: datetime
    classes: List[ProjectClass] = []

    class Config:
        from_attributes = True

class ImageBase(BaseModel):
    filename: str
    relative_path: str
    width: int
    height: int
    file_size_bytes: int

class Image(ImageBase):
    id: int
    project_id: int
    status: str
    review_status: str
    confidence: Optional[float] = None
    agreement_score: Optional[float] = None
    mask_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewer_notes: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AnnotationBase(BaseModel):
    class_name: str
    model_source: str
    confidence: Optional[float] = None
    segmentation_json: Optional[str] = None
    bbox_json: Optional[str] = None

class AnnotationCreate(AnnotationBase):
    pass

class Annotation(AnnotationBase):
    id: int
    image_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_images: int
    processed_images: int
    remaining_images: int
    queue_size: int
    
    review_tasks_sent: int
    review_tasks_reviewed: int
    review_tasks_corrected: int
    review_tasks_pending: int
    review_tasks_rejected: int
    
    avg_confidence: float
    class_distribution: Dict[str, int]
    
    engine_state: str
    hardware: Dict[str, Any]

class QueueStatus(BaseModel):
    pending: int
    processing: int
    completed: int
    failed: int
    processing_speed_ips: float # images per second
    eta_seconds: int

class RejectRequest(BaseModel):
    reason: str
    notes: Optional[str] = None
