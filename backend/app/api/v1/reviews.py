from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models import ImageryAnalysis, SpatialFeature, DetectionReview, AnalysisReview, ProcessingJob, User
from app.schemas import (
    ReviewUpsertRequest, ReviewResponse, ReviewSummary, ReviewListResponse,
    AnalysisReviewRequest, AnalysisReviewResponse,
    REVIEW_STATUSES, AI_CLASS_CHOICES,
)

router = APIRouter()

IMAGE_REVIEW_STATUSES = {"accepted", "needs_relabel", "rejected"}


def _serialize_image_review(r: AnalysisReview) -> AnalysisReviewResponse:
    return AnalysisReviewResponse(
        id=r.id, analysis_id=r.analysis_id, reviewer_id=r.reviewer_id,
        reviewer_email=r.reviewer.email if r.reviewer else None,
        status=r.status, comment=r.comment, review_source=r.review_source,
        resent=bool(r.resent), resent_job_id=r.resent_job_id, reviewed_at=r.reviewed_at,
    )


def _serialize(review: DetectionReview) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        analysis_id=review.analysis_id,
        feature_id=review.feature_id,
        reviewer_id=review.reviewer_id,
        reviewer_email=review.reviewer.email if review.reviewer else None,
        original_label=review.original_label,
        original_source=review.original_source,
        corrected_label=review.corrected_label,
        review_source=review.review_source,
        status=review.status,
        comment=review.comment,
        reviewed_at=review.reviewed_at,
    )


def _build_summary(db: Session, analysis_id: int) -> ReviewSummary:
    total = db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis_id).count()
    reviews = db.query(DetectionReview).filter(DetectionReview.analysis_id == analysis_id).all()
    accepted = sum(1 for r in reviews if r.status == "accepted")
    needs_relabel = sum(1 for r in reviews if r.status == "needs_relabel")
    rejected = sum(1 for r in reviews if r.status == "rejected")
    reviewed = accepted + needs_relabel + rejected
    pending = max(0, total - reviewed)
    progress = round((reviewed / total) * 100, 1) if total else 0.0
    return ReviewSummary(
        total_features=total, reviewed=reviewed, pending=pending,
        accepted=accepted, needs_relabel=needs_relabel, rejected=rejected,
        progress_pct=progress,
    )


@router.get("/analyses/{analysis_id}/reviews", response_model=ReviewListResponse)
def list_reviews(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any authenticated role may read
):
    """List all human reviews for an analysis plus an aggregate review summary."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    reviews = (
        db.query(DetectionReview)
        .filter(DetectionReview.analysis_id == analysis_id)
        .order_by(DetectionReview.feature_id.asc())
        .all()
    )
    image_review = db.query(AnalysisReview).filter(AnalysisReview.analysis_id == analysis_id).first()
    return ReviewListResponse(
        analysis_id=analysis_id,
        summary=_build_summary(db, analysis_id),
        reviews=[_serialize(r) for r in reviews],
        image_review=_serialize_image_review(image_review) if image_review else None,
    )


@router.put("/analyses/{analysis_id}/image-review", response_model=AnalysisReviewResponse)
def upsert_image_review(
    analysis_id: int,
    payload: AnalysisReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"])),  # viewers are read-only
):
    """
    Record a single whole-image verdict (accept / needs_relabel / reject).

    When the verdict is 'needs_relabel' (the classes were not detected properly), the ENTIRE
    image is re-sent through the processing pipeline for a fresh run. The AI output is never
    silently mutated; this is a QA verdict + a re-processing trigger.
    """
    status = (payload.status or "").lower()
    if status not in IMAGE_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(IMAGE_REVIEW_STATUSES)}")

    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    review = db.query(AnalysisReview).filter(AnalysisReview.analysis_id == analysis_id).first()
    if review is None:
        review = AnalysisReview(analysis_id=analysis_id)
        db.add(review)

    review.status = status
    review.comment = payload.comment
    review.reviewer_id = current_user.id
    review.review_source = "human_review"
    review.reviewed_at = datetime.now(timezone.utc)

    # "needs_relabel" -> re-send the whole image through the pipeline
    resent_job_id = None
    if status == "needs_relabel":
        job = ProcessingJob(
            analysis_id=analysis_id, job_type="analysis", status="queued",
            current_stage="VALIDATING", message="Re-sent by reviewer (image-level relabel)",
        )
        db.add(job)
        db.flush()
        resent_job_id = job.id
        review.resent = True
        review.resent_job_id = resent_job_id
        analysis.status = "pending"
        db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis_id).delete()

    db.commit()
    db.refresh(review)

    if resent_job_id is not None:
        # Kick off reprocessing after the verdict is committed
        try:
            from app.workers.tasks import process_imagery_analysis
            process_imagery_analysis.delay(analysis_id, resent_job_id)
        except Exception:
            pass  # job row exists; a worker/retry can still pick it up

    return _serialize_image_review(review)


@router.put("/analyses/{analysis_id}/features/{feature_id}/review", response_model=ReviewResponse)
def upsert_feature_review(
    analysis_id: int,
    feature_id: int,
    payload: ReviewUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"])),  # viewers are read-only
):
    """
    Create or update the human review for a single detected feature.

    Provenance is preserved: the original AI label/source is captured once (from the feature)
    and never overwritten; corrections are stored separately.
    """
    status = (payload.status or "").lower()
    if status not in REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(REVIEW_STATUSES)}")

    corrected = payload.corrected_label
    if status == "needs_relabel":
        if not corrected:
            raise HTTPException(status_code=400, detail="corrected_label is required when status is 'needs_relabel'")
        if corrected not in AI_CLASS_CHOICES:
            raise HTTPException(status_code=400, detail=f"Invalid corrected_label. Allowed: {AI_CLASS_CHOICES}")
    else:
        corrected = None  # only relabel carries a corrected label

    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    feature = (
        db.query(SpatialFeature)
        .filter(SpatialFeature.id == feature_id, SpatialFeature.analysis_id == analysis_id)
        .first()
    )
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found for this analysis")

    review = db.query(DetectionReview).filter(DetectionReview.feature_id == feature_id).first()
    now = datetime.now(timezone.utc)
    if review is None:
        review = DetectionReview(
            analysis_id=analysis_id,
            feature_id=feature_id,
            original_label=feature.class_name,   # provenance captured once
            original_source=feature.source,
        )
        db.add(review)

    review.status = status
    review.corrected_label = corrected
    review.comment = payload.comment
    review.reviewer_id = current_user.id
    review.review_source = "human_review"
    review.reviewed_at = now
    db.commit()
    db.refresh(review)
    return _serialize(review)
