import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Annotation, Image, PredictionVsCorrection, Project


# Confusion pairs tracked for active learning (PRD-specified)
TRACKED_CONFUSION_PAIRS = [
    ("building", "tree_cover"),
    ("tree_cover", "building"),
    ("road", "bare_ground"),
    ("water_body", "shadow"),
    ("hospital", "public_building"),
    ("school", "public_building"),
]


class ActiveLearningService:
    @staticmethod
    def corrections_dir(project: Project) -> str:
        path = os.path.join(project.root_path, "corrections_dataset")
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "images"), exist_ok=True)
        os.makedirs(os.path.join(path, "masks"), exist_ok=True)
        os.makedirs(os.path.join(path, "metadata"), exist_ok=True)
        return path

    @classmethod
    def log_correction(
        cls,
        db: Session,
        image: Image,
        predicted_class: str,
        corrected_class: str,
        correction_type: str,
        region_id: Optional[str] = None,
        confidence: Optional[float] = None,
        reviewer: Optional[str] = None,
        original_json: Optional[dict] = None,
        corrected_json: Optional[dict] = None,
    ) -> PredictionVsCorrection:
        record = PredictionVsCorrection(
            image_id=image.id,
            original_prediction_json=json.dumps(original_json or {}),
            human_correction_json=json.dumps(corrected_json or {}),
            correction_type=correction_type,
            region_id=region_id,
            predicted_class=predicted_class,
            corrected_class=corrected_class,
            confidence=confidence,
            reviewer=reviewer,
        )
        db.add(record)
        db.flush()
        return record

    @classmethod
    def save_correction_patch(
        cls,
        project: Project,
        image: Image,
        predicted_class: str,
        corrected_class: str,
        polygon_points: List[List[float]],
        confidence: float,
        region_id: str,
    ) -> str:
        """Write image patch + mask to corrections_dataset/."""
        base_dir = cls.corrections_dir(project)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stem = f"{image.id}_{region_id}_{ts}"

        orig = cv2.imread(image.absolute_path)
        if orig is None:
            return ""

        h, w = orig.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(polygon_points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], 255)

        x, y, bw, bh = cv2.boundingRect(pts)
        pad = 16
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w, x + bw + pad)
        y2 = min(h, y + bh + pad)

        patch = orig[y1:y2, x1:x2]
        patch_mask = mask[y1:y2, x1:x2]

        img_path = os.path.join(base_dir, "images", f"{stem}.png")
        mask_path = os.path.join(base_dir, "masks", f"{stem}.png")
        meta_path = os.path.join(base_dir, "metadata", f"{stem}.json")

        cv2.imwrite(img_path, patch)
        cv2.imwrite(mask_path, patch_mask)

        meta = {
            "image_id": image.id,
            "filename": image.filename,
            "region_id": region_id,
            "predicted_class": predicted_class,
            "corrected_class": corrected_class,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
            "tracked_pair": (predicted_class, corrected_class)
            in TRACKED_CONFUSION_PAIRS,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return img_path

    @classmethod
    def get_confusion_matrix(cls, db: Session, project_id: int) -> Dict[str, Dict[str, int]]:
        rows = (
            db.query(PredictionVsCorrection)
            .join(Image)
            .filter(
                Image.project_id == project_id,
                PredictionVsCorrection.predicted_class.isnot(None),
                PredictionVsCorrection.corrected_class.isnot(None),
            )
            .all()
        )
        matrix: Dict[str, Dict[str, int]] = {}
        for row in rows:
            pred = row.predicted_class or "unlabeled"
            corr = row.corrected_class or "unlabeled"
            if pred == corr:
                continue
            matrix.setdefault(pred, {})
            matrix[pred][corr] = matrix[pred].get(corr, 0) + 1
        return matrix

    @classmethod
    def process_manual_corrections(
        cls,
        db: Session,
        project: Project,
        image: Image,
        ai_annotations: List[Annotation],
        corrected_annotations: List[dict],
        reviewer: str = "manual_review",
    ) -> int:
        corrections = 0
        ai_by_id = {ann.id: ann for ann in ai_annotations}
        matched_ai_ids = set()

        for idx, corrected in enumerate(corrected_annotations):
            human_class = corrected.get("class_name")
            raw_points = corrected.get("segmentation") or []
            points = [
                [float(point[0]), float(point[1])]
                for point in raw_points
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            if not human_class or len(points) < 3:
                continue

            annotation_id = corrected.get("id")
            ai_ann = ai_by_id.get(annotation_id) if annotation_id else None
            region_id = str(annotation_id or f"manual_region_{idx}")

            if not ai_ann:
                cls.log_correction(
                    db,
                    image,
                    predicted_class="missed_by_ai",
                    corrected_class=human_class,
                    correction_type="new_region",
                    region_id=region_id,
                    reviewer=reviewer,
                    corrected_json={"class_name": human_class, "segmentation": points},
                )
                cls.save_correction_patch(
                    project,
                    image,
                    "missed_by_ai",
                    human_class,
                    points,
                    1.0,
                    region_id,
                )
                corrections += 1
                continue

            matched_ai_ids.add(ai_ann.id)
            predicted = ai_ann.class_name
            original_points = json.loads(ai_ann.segmentation_json or "[]")
            mask_changed = original_points != points
            class_changed = predicted != human_class
            if class_changed or mask_changed:
                cls.log_correction(
                    db,
                    image,
                    predicted_class=predicted,
                    corrected_class=human_class,
                    correction_type="class_change" if class_changed else "mask_edit",
                    region_id=region_id,
                    confidence=ai_ann.confidence,
                    reviewer=reviewer,
                    original_json={"class_name": predicted, "segmentation": original_points},
                    corrected_json={"class_name": human_class, "segmentation": points},
                )
                cls.save_correction_patch(
                    project,
                    image,
                    predicted,
                    human_class,
                    points,
                    float(ai_ann.confidence or 0.0),
                    region_id,
                )
                corrections += 1

        for annotation_id, ai_ann in ai_by_id.items():
            if annotation_id not in matched_ai_ids:
                cls.log_correction(
                    db,
                    image,
                    predicted_class=ai_ann.class_name,
                    corrected_class="deleted",
                    correction_type="delete_region",
                    region_id=str(annotation_id),
                    confidence=ai_ann.confidence,
                    reviewer=reviewer,
                    original_json={"class_name": ai_ann.class_name},
                )
                corrections += 1

        if corrections > 0:
            image.review_status = "human_corrected"
            image.correction_count = (image.correction_count or 0) + corrections
        else:
            image.review_status = "reviewed"

        image.reviewer = reviewer
        image.last_viewed = datetime.utcnow()
        db.commit()
        return corrections
