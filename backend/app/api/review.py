from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Project, Image, ReviewLog, ProcessingQueue, Annotation
from app.schemas import Image as ImageSchema, RejectRequest, Annotation as AnnotationSchema

router = APIRouter()

class CorrectionRequest(BaseModel):
    annotations: List[Dict[str, Any]]

@router.get("/{project_id}/review-queue", response_model=List[ImageSchema])
def get_review_queue(project_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    # Returns all images that have not yet been reviewed at least once
    images = db.query(Image).filter(
        Image.project_id == project_id,
        Image.status == "completed",
        Image.review_status == "pending_review"
    ).order_by(Image.id.asc()).offset(skip).limit(limit).all()
    return images

@router.get("/{project_id}/debug-images", response_model=List[ImageSchema])
def get_debug_images(project_id: int, db: Session = Depends(get_db)):
    return db.query(Image).filter(Image.project_id == project_id).all()

@router.post("/{project_id}/force-populate")
def force_populate_queue(project_id: int, db: Session = Depends(get_db)):
    # Move all completed images to pending_review
    images = db.query(Image).filter(
        Image.project_id == project_id,
        Image.status == "completed"
    ).all()
    
    count = 0
    for img in images:
        img.review_status = "pending_review"
        count += 1
        
    db.commit()
    return {"message": f"Forced {count} images into pending_review queue"}

@router.get("/{project_id}/images/{image_id}/annotations", response_model=List[AnnotationSchema])
def get_annotations(project_id: int, image_id: int, db: Session = Depends(get_db)):
    annotations = db.query(Annotation).filter(Annotation.image_id == image_id).all()
    return annotations

@router.post("/{project_id}/images/{image_id}/mark-viewed")
def mark_image_viewed(project_id: int, image_id: int, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    from datetime import datetime
    image.last_viewed = datetime.utcnow()
    image.reviewer = "default_reviewer"
    
    if image.review_status == "pending_review":
        image.review_status = "reviewed"
        
        # Log auto-acceptance by reviewer
        db.add(ReviewLog(
            image_id=image.id,
            action="reviewed",
            notes="Image viewed in review queue"
        ))
        db.commit()
    else:
        db.commit()
    return {"status": "ok"}

@router.post("/{project_id}/images/{image_id}/correct")
def correct_image(project_id: int, image_id: int, req: CorrectionRequest, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    image.review_status = "human_corrected"
    image.correction_count = (image.correction_count or 0) + 1

    # Get old annotations to track confusion
    old_annotations = db.query(Annotation).filter(Annotation.image_id == image_id).all()
    predicted_class = old_annotations[0].class_name if old_annotations else None

    # Delete existing annotations and replace with corrected ones
    for ann in old_annotations:
        db.delete(ann)
    
    actual_class = None
    for ann_data in req.annotations:
        import json
        new_class = ann_data.get("class_name")
        if not actual_class:
            actual_class = new_class
        new_ann = Annotation(
            image_id=image.id,
            class_name=new_class,
            model_source="Human Corrected",
            confidence=1.0,
            segmentation_json=json.dumps(ann_data.get("segmentation", [])),
            bbox_json=json.dumps(ann_data.get("bbox", []))
        )
        db.add(new_ann)

    db.add(ReviewLog(
        image_id=image.id,
        action="corrected",
        notes="Human corrected",
        predicted_class=predicted_class,
        actual_class=actual_class
    ))

    db.commit()
    return {"status": "ok"}

@router.post("/{project_id}/images/{image_id}/reject")
def reject_image(project_id: int, image_id: int, req: RejectRequest, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    image.review_status = "rejected"
    image.rejection_reason = req.reason
    image.reviewer_notes = req.notes
    image.retry_count = (image.retry_count or 0) + 1
    
    # Log rejection
    db.add(ReviewLog(
        image_id=image.id,
        action="rejected",
        reason=req.reason,
        notes=req.notes
    ))
    
    # Optionally auto-enqueue for relabeling if needed by project settings
    existing_q = db.query(ProcessingQueue).filter(ProcessingQueue.image_id == image.id).first()
    if existing_q:
        existing_q.status = "pending"
    else:
        db.add(ProcessingQueue(image_id=image.id))
        
    image.status = "pending"
    
    db.commit()
    return {"message": "Image rejected and queued for relabeling"}


