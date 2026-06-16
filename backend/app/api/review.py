from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.core.database import get_db
from app.models import Image, ReviewLog, ProcessingQueue, Annotation
from app.schemas import Image as ImageSchema, RejectRequest, Annotation as AnnotationSchema
from app.services.active_learning import ActiveLearningService

router = APIRouter()

class CorrectionRequest(BaseModel):
    annotations: List[Dict[str, Any]]
    reviewer: str = "manual_review"
    notes: Optional[str] = None

class ApprovalRequest(BaseModel):
    reviewer: str = "manual_review"
    notes: Optional[str] = None

@router.get("/{project_id}/review-queue", response_model=List[ImageSchema])
def get_review_queue(project_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    images = db.query(Image).filter(
        Image.project_id == project_id,
        Image.status == "completed",
        Image.review_status == "pending_review",
        Image.is_corrupt == False,
        Image.is_duplicate == False,
    ).order_by(Image.id.asc()).offset(skip).limit(limit).all()
    return images

@router.get("/{project_id}/debug-images", response_model=List[ImageSchema])
def get_debug_images(project_id: int, db: Session = Depends(get_db)):
    return db.query(Image).filter(Image.project_id == project_id).all()

@router.post("/{project_id}/force-populate")
def force_populate_queue(project_id: int, db: Session = Depends(get_db)):
    images = db.query(Image).filter(
        Image.project_id == project_id,
        Image.status == "completed",
        Image.is_corrupt == False,
        Image.is_duplicate == False,
    ).all()
    
    count = 0
    for img in images:
        img.review_status = "pending_review"
        count += 1
        
    db.commit()
    return {"message": f"Forced {count} images into pending_review queue"}

@router.get("/{project_id}/confusion-matrix")
def get_confusion_matrix(project_id: int, db: Session = Depends(get_db)):
    return ActiveLearningService.get_confusion_matrix(db, project_id)

@router.get("/{project_id}/images/{image_id}/annotations", response_model=List[AnnotationSchema])
def get_annotations(project_id: int, image_id: int, db: Session = Depends(get_db)):
    annotations = db.query(Annotation).filter(Annotation.image_id == image_id).all()
    return annotations

@router.post("/{project_id}/images/{image_id}/mark-viewed")
def mark_image_viewed(project_id: int, image_id: int, req: ApprovalRequest = ApprovalRequest(), db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    from datetime import datetime
    image.last_viewed = datetime.utcnow()
    image.reviewer = req.reviewer
    
    if image.review_status == "pending_review":
        image.review_status = "reviewed"
        
        db.add(ReviewLog(
            image_id=image.id,
            action="approved",
            notes=req.notes or "Human approved without correction"
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

    old_annotations = db.query(Annotation).filter(Annotation.image_id == image_id).all()
    corrections = ActiveLearningService.process_manual_corrections(
        db,
        image.project,
        image,
        old_annotations,
        req.annotations,
        reviewer=req.reviewer,
    )

    for ann in old_annotations:
        db.delete(ann)
    
    import json
    actual_class = None
    for ann_data in req.annotations:
        new_class = ann_data.get("class_name")
        segmentation = ann_data.get("segmentation", [])
        if not new_class or len(segmentation) < 3:
            continue
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
        notes=req.notes or f"Human corrected {corrections} region(s) via manual review",
        actual_class=actual_class
    ))

    image.review_status = "human_corrected"
    image.correction_count = (image.correction_count or 0) + corrections
    image.reviewer = req.reviewer
    db.commit()
    return {"status": "ok", "corrections_logged": corrections}

@router.post("/{project_id}/images/{image_id}/reject")
def reject_image(project_id: int, image_id: int, req: RejectRequest, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id, Image.project_id == project_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    image.review_status = "rejected"
    image.rejection_reason = req.reason
    image.reviewer_notes = req.notes
    image.retry_count = (image.retry_count or 0) + 1

    old_annotations = db.query(Annotation).filter(Annotation.image_id == image.id).all()
    for ann in old_annotations:
        ActiveLearningService.log_correction(
            db,
            image,
            predicted_class=ann.class_name,
            corrected_class=req.reason,
            correction_type="rejected_for_relabel",
            region_id=str(ann.id),
            confidence=ann.confidence,
            reviewer="manual_review",
            original_json={
                "class_name": ann.class_name,
                "segmentation": ann.segmentation_json,
                "bbox": ann.bbox_json,
            },
            corrected_json={"reason": req.reason, "notes": req.notes},
        )
    
    db.add(ReviewLog(
        image_id=image.id,
        action="rejected",
        reason=req.reason,
        notes=req.notes
    ))
    
    existing_q = db.query(ProcessingQueue).filter(ProcessingQueue.image_id == image.id).first()
    if existing_q:
        existing_q.status = "pending"
        existing_q.attempt_number = 1
    else:
        db.add(ProcessingQueue(image_id=image.id))
        
    image.status = "pending"
    
    db.commit()
    return {"message": "Image rejected and queued for relabeling"}
