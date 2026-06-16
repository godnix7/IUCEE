import json
import math
import threading
import time
from datetime import datetime
from typing import Dict, List

import cv2
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Annotation, Image, PredictionVsCorrection, ProcessingQueue, ReviewLog
from app.services.model_service import ModelService
from app.services.segmentation_artifact_service import SegmentationArtifactService
from app.services.tiling_service import TilingService


class ProcessingService:
    _instance = None
    _lock = threading.Lock()
    _is_running = False
    _is_paused = False
    _thread = None
    _inference_times = []

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProcessingService, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_performance_stats(cls):
        if not cls._inference_times:
            return {"avg_inference_ms": 0, "images_per_minute": 0}

        avg_time_sec = sum(cls._inference_times) / len(cls._inference_times)
        ipm = 60.0 / avg_time_sec if avg_time_sec > 0 else 0
        return {
            "avg_inference_ms": round(avg_time_sec * 1000, 2),
            "images_per_minute": round(ipm, 1),
        }

    @classmethod
    def get_state(cls):
        if not cls._is_running:
            return "STOPPED"
        if cls._is_paused:
            return "PAUSED"
        return "RUNNING"

    def start_worker(self):
        ProcessingService._is_paused = False
        if not ProcessingService._is_running:
            ProcessingService._is_running = True
            ProcessingService._thread = threading.Thread(target=self._worker_loop, daemon=True)
            ProcessingService._thread.start()
            print("Background processing worker started.")

    def pause_worker(self):
        ProcessingService._is_paused = True

    def resume_worker(self):
        ProcessingService._is_paused = False

    def stop_worker(self):
        ProcessingService._is_running = False
        ProcessingService._is_paused = False
        try:
            db = SessionLocal()
            db.query(ProcessingQueue).filter(ProcessingQueue.status == "pending").delete()
            db.commit()
            db.close()
            print("Processing Queue cancelled.")
        except Exception as exc:
            print(f"Error clearing processing queue: {exc}")

    def _worker_loop(self):
        while ProcessingService._is_running:
            if ProcessingService._is_paused:
                time.sleep(1)
                continue

            try:
                db = SessionLocal()
                queue_item = (
                    db.query(ProcessingQueue)
                    .filter(ProcessingQueue.status == "pending")
                    .first()
                )

                if not queue_item:
                    db.close()
                    time.sleep(1)
                    continue

                self._process_image(db, queue_item)
                db.close()
            except Exception as exc:
                print(f"Error in processing worker loop: {exc}")
                time.sleep(2)

    @staticmethod
    def _class_index(project_classes: List[str], name: str) -> int:
        try:
            return project_classes.index(name)
        except ValueError:
            return -1

    @staticmethod
    def _parse_polygon(annotation: Annotation) -> List[List[float]]:
        if not annotation.segmentation_json:
            return []
        try:
            points = json.loads(annotation.segmentation_json)
        except json.JSONDecodeError:
            return []
        return [
            [float(point[0]), float(point[1])]
            for point in points
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]

    @staticmethod
    def _mentioned_classes(text: str, project_classes: List[str]) -> List[str]:
        normalized = (text or "").lower().replace("-", "_").replace(" ", "_")
        return [class_name for class_name in project_classes if class_name.lower() in normalized]

    @classmethod
    def _apply_relabel_feedback(
        cls,
        p_fused: np.ndarray,
        image: Image,
        previous_annotations: List[Annotation],
        project_classes: List[str],
    ) -> List[str]:
        if not previous_annotations or not (image.retry_count or 0):
            return []

        feedback_notes: List[str] = []
        class_to_idx = {class_name: idx for idx, class_name in enumerate(project_classes)}
        mentioned_classes = cls._mentioned_classes(
            f"{image.rejection_reason or ''} {image.reviewer_notes or ''}",
            project_classes,
        )

        for annotation in previous_annotations:
            predicted_idx = class_to_idx.get(annotation.class_name)
            points = cls._parse_polygon(annotation)
            if predicted_idx is None or len(points) < 3:
                continue

            mask = np.zeros(p_fused.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [np.array(points, dtype=np.int32).reshape((-1, 1, 2))], 1)
            region = mask == 1
            if not np.any(region):
                continue

            target_class = None
            if mentioned_classes:
                target_class = mentioned_classes[0]
            elif annotation.bbox_json:
                try:
                    meta = json.loads(annotation.bbox_json)
                    alt_class = meta.get("alt_class")
                    if alt_class in class_to_idx and alt_class != annotation.class_name:
                        target_class = alt_class
                except json.JSONDecodeError:
                    target_class = None

            p_fused[region, predicted_idx] *= 0.35
            if target_class and target_class in class_to_idx:
                p_fused[region, class_to_idx[target_class]] += 0.45
                feedback_notes.append(f"suppressed {annotation.class_name}, boosted {target_class}")
            else:
                feedback_notes.append(f"suppressed repeated {annotation.class_name}")

        if mentioned_classes:
            low_confidence = np.max(p_fused, axis=-1) < 0.70
            for class_name in mentioned_classes:
                p_fused[low_confidence, class_to_idx[class_name]] += 0.08
                feedback_notes.append(f"boosted rejected-note class {class_name}")

        p_fused /= np.maximum(np.sum(p_fused, axis=-1, keepdims=True), 1e-6)
        return feedback_notes

    @staticmethod
    def _class_error_rates(db: Session) -> Dict[str, float]:
        try:
            total_preds = (
                db.query(PredictionVsCorrection.predicted_class, func.count(PredictionVsCorrection.id))
                .filter(PredictionVsCorrection.predicted_class.isnot(None))
                .group_by(PredictionVsCorrection.predicted_class)
                .all()
            )
            misclass_preds = (
                db.query(PredictionVsCorrection.predicted_class, func.count(PredictionVsCorrection.id))
                .filter(
                    PredictionVsCorrection.predicted_class.isnot(None),
                    PredictionVsCorrection.predicted_class != PredictionVsCorrection.corrected_class,
                )
                .group_by(PredictionVsCorrection.predicted_class)
                .all()
            )
            total_dict = {row[0]: row[1] for row in total_preds if row[0]}
            misclass_dict = {row[0]: row[1] for row in misclass_preds if row[0]}
            return {
                class_name: misclass_dict.get(class_name, 0) / total
                for class_name, total in total_dict.items()
                if total >= settings.MIN_SAMPLES_FOR_PENALTY
            }
        except Exception as exc:
            print(f"Error fetching active learning stats: {exc}")
            return {}

    def _process_image(self, db: Session, queue_item: ProcessingQueue):
        start_t = time.time()
        queue_item.status = "processing"
        queue_item.started_at = datetime.utcnow()

        image = db.query(Image).filter(Image.id == queue_item.image_id).first()
        if image:
            if image.is_corrupt or image.is_duplicate:
                queue_item.status = "completed"
                queue_item.completed_at = datetime.utcnow()
                queue_item.error_message = "Skipped: corrupt or duplicate"
                image.status = "failed" if image.is_corrupt else "completed"
                db.commit()
                return
            image.status = "processing"

        db.commit()

        try:
            project_classes = [
                project_class.name
                for project_class in image.project.classes
                if project_class.name.lower() != "unknown"
            ] or ["object"]
            previous_annotations = db.query(Annotation).filter(Annotation.image_id == image.id).all()

            orig_img = cv2.imread(image.absolute_path)
            orig_h, orig_w = orig_img.shape[:2] if orig_img is not None else (1024, 1024)

            p_fused, tiles = TilingService.run_ensemble_on_tiles(
                image.absolute_path,
                orig_h,
                orig_w,
                project_classes,
            )
            TilingService.persist_tile_metadata(db, image.id, tiles)
            feedback_notes = self._apply_relabel_feedback(
                p_fused,
                image,
                previous_annotations,
                project_classes,
            )

            label_map = np.argmax(p_fused, axis=-1).astype(np.int32)
            confidence_map = np.max(p_fused, axis=-1)

            sam_regions = ModelService.generate_sam_regions(image.absolute_path, orig_h, orig_w)
            for region_id in np.unique(sam_regions):
                region_mask = sam_regions == region_id
                region_labels = label_map[region_mask]
                if len(region_labels) > 0:
                    label_map[region_mask] = np.bincount(region_labels).argmax()

            vehicle_idx = self._class_index(project_classes, "vehicle")
            road_idx = self._class_index(project_classes, "road")
            if road_idx >= 0:
                road_mask = (label_map == road_idx).astype(np.uint8)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
                closed_road = cv2.morphologyEx(road_mask, cv2.MORPH_CLOSE, kernel)
                added_road = (closed_road == 1) & (road_mask == 0)
                label_map[added_road] = road_idx
                confidence_map[added_road] = 0.65

            class_error_rates = self._class_error_rates(db)

            label_map = cv2.medianBlur(label_map.astype(np.uint8), 5)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(label_map, connectivity=8)
            shadow_idx = self._class_index(project_classes, "shadow")

            for label_id in range(1, num_labels):
                if stats[label_id, cv2.CC_STAT_AREA] < 200:
                    region_class = int(np.median(label_map[labels == label_id]))
                    if region_class not in (shadow_idx, vehicle_idx):
                        label_map[labels == label_id] = 0

            building_idx = self._class_index(project_classes, "building")
            tree_idx = self._class_index(project_classes, "tree_cover")
            water_idx = self._class_index(project_classes, "water_body")
            slum_idx = self._class_index(project_classes, "slum_area")
            hospital_idx = self._class_index(project_classes, "hospital")
            school_idx = self._class_index(project_classes, "school")
            substation_idx = self._class_index(project_classes, "electrical_substation")
            construction_idx = self._class_index(project_classes, "construction_area")

            final_annotations_to_add = []
            all_confidences = []

            for class_idx, class_name_temp in enumerate(project_classes):
                class_mask = (label_map == class_idx).astype(np.uint8) * 255
                contours, _ = cv2.findContours(class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area <= 50:
                        continue

                    mask_contour = np.zeros_like(class_mask)
                    cv2.drawContours(mask_contour, [contour], -1, 255, -1)
                    region_conf = float(np.mean(confidence_map[mask_contour == 255]))
                    if math.isnan(region_conf):
                        region_conf = 0.5

                    if class_idx == building_idx:
                        rect = cv2.minAreaRect(contour)
                        box = cv2.boxPoints(rect)
                        rect_area = cv2.contourArea(box)
                        if rect_area > 0 and (area / rect_area) < 0.6:
                            region_conf = max(0.1, region_conf - 0.4)
                    elif class_idx == tree_idx:
                        perimeter = cv2.arcLength(contour, True)
                        if perimeter > 0:
                            circularity = (4 * math.pi * area) / (perimeter * perimeter)
                            if circularity > 0.6:
                                region_conf = min(0.95, region_conf + 0.1)
                    elif class_idx == road_idx:
                        rect = cv2.minAreaRect(contour)
                        width, height = rect[1]
                        if width > 0 and height > 0:
                            aspect_ratio = max(width / height, height / width)
                            region_conf = min(0.95, region_conf + 0.1) if aspect_ratio > 3.0 else max(0.1, region_conf - 0.2)
                    elif class_idx == water_idx:
                        hull = cv2.convexHull(contour)
                        hull_area = cv2.contourArea(hull)
                        if hull_area > 0:
                            solidity = float(area) / hull_area
                            region_conf = min(0.95, region_conf + 0.1) if solidity > 0.85 else max(0.1, region_conf - 0.3)
                    elif class_idx == slum_idx and area < 500:
                        region_conf = max(0.1, region_conf - 0.25)
                    elif class_idx in (hospital_idx, school_idx) and area < 800:
                        region_conf = max(0.1, region_conf - 0.2)
                    elif class_idx == substation_idx:
                        rect = cv2.minAreaRect(contour)
                        width, height = rect[1]
                        if width > 0 and height > 0 and max(width, height) / min(width, height) < 1.5 and area < 200:
                            region_conf = max(0.1, region_conf - 0.3)
                    elif class_idx == construction_idx:
                        perimeter = cv2.arcLength(contour, True)
                        if perimeter > 0:
                            circularity = (4 * math.pi * area) / (perimeter * perimeter)
                            if circularity > 0.7:
                                region_conf = max(0.1, region_conf - 0.2)

                    if class_name_temp in class_error_rates and class_error_rates[class_name_temp] > 0.5:
                        region_conf = max(0.1, region_conf - settings.ACTIVE_LEARNING_PENALTY)

                    epsilon = 0.002 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    if len(approx) < 3:
                        continue

                    polygon = [[float(point[0][0]), float(point[0][1])] for point in approx]
                    x, y, width, height = cv2.boundingRect(contour)
                    region_probs = p_fused[mask_contour == 255]
                    if len(region_probs) > 0:
                        avg_probs = np.mean(region_probs, axis=0)
                        sorted_indices = np.argsort(avg_probs)[::-1]
                        alt_class_idx = sorted_indices[1] if len(sorted_indices) > 1 else sorted_indices[0]
                        alt_class = project_classes[alt_class_idx] if alt_class_idx < len(project_classes) else class_name_temp
                    else:
                        alt_class = class_name_temp

                    final_annotations_to_add.append(
                        Annotation(
                            image_id=image.id,
                            class_name=class_name_temp,
                            model_source="Ensemble-Semantic-Seg",
                            confidence=region_conf,
                            segmentation_json=json.dumps(polygon),
                            bbox_json=json.dumps(
                                {
                                    "bbox": [int(x), int(y), int(width), int(height)],
                                    "area": area,
                                    "alt_class": alt_class,
                                    "agreement": region_conf,
                                    "needs_attention": region_conf < settings.CONFIDENCE_UNKNOWN_THRESHOLD,
                                }
                            ),
                        )
                    )
                    all_confidences.append(region_conf)

            class_stats = {}
            for annotation in final_annotations_to_add:
                class_stats[annotation.class_name] = class_stats.get(annotation.class_name, 0) + 1

            SegmentationArtifactService.save_mask_overlay(
                image.project_id,
                image,
                label_map.astype(np.uint8),
                project_classes,
            )
            SegmentationArtifactService.save_confidence_map(image.project_id, image, confidence_map)

            avg_conf = float(np.mean(confidence_map))
            audit_block = (
                f"**AERIAL PIPELINE AUDIT**\n"
                f"- Mode: {'SegFormer-GPU' if ModelService.is_real_mode_active() else 'Simulation'}\n"
                f"- Tiling: {settings.TILE_SIZE}x{settings.TILE_SIZE}, overlap {settings.TILE_OVERLAP * 100}%\n"
                f"- Tiles Processed: {len(tiles)}\n"
                f"- Semantic masks only; no rectangular detector output\n"
                f"- SAM Refinement Applied\n"
                f"- Class stats: {class_stats}\n"
            )
            if feedback_notes:
                audit_block += f"- Relabel feedback applied: {feedback_notes}\n"

            db.query(Annotation).filter(Annotation.image_id == image.id).delete()
            for annotation in final_annotations_to_add:
                db.add(annotation)
                db.flush()

            queue_item.status = "completed"
            queue_item.completed_at = datetime.utcnow()
            image.status = "completed"
            overall_img_conf = sum(all_confidences) / len(all_confidences) if all_confidences else avg_conf
            image.confidence = overall_img_conf
            image.agreement_score = overall_img_conf
            image.review_status = "pending_review"
            image.rejection_reason = None
            image.reviewer_notes = audit_block + "\n- Status: Requires human review"

            db.add(
                ReviewLog(
                    image_id=image.id,
                    action="processed_and_routed",
                    notes=image.reviewer_notes,
                )
            )

            db.commit()

            processing_time = time.time() - start_t
            cls = type(self)
            cls._inference_times.append(processing_time)
            if len(cls._inference_times) > 20:
                cls._inference_times.pop(0)

        except Exception as exc:
            db.rollback()
            queue_item.attempt_number += 1
            if queue_item.attempt_number >= settings.MAX_RETRIES:
                queue_item.status = "failed"
                queue_item.error_message = str(exc)
                queue_item.completed_at = datetime.utcnow()
                if image:
                    image.status = "failed"
                    image.review_status = "manual_review"
            else:
                queue_item.status = "pending"
            db.commit()

    @staticmethod
    def enqueue_all(db: Session, project_id: int) -> int:
        images = (
            db.query(Image)
            .filter(
                Image.project_id == project_id,
                Image.status.in_(["pending", "failed"]),
                Image.is_corrupt == False,
                Image.is_duplicate == False,
            )
            .all()
        )

        count = 0
        for image in images:
            existing = db.query(ProcessingQueue).filter(ProcessingQueue.image_id == image.id).first()
            if not existing:
                db.add(ProcessingQueue(image_id=image.id))
                count += 1
            elif existing.status in ["completed", "failed"]:
                existing.status = "pending"
                existing.attempt_number = 1
                count += 1

            image.status = "pending"

        db.commit()

        service = ProcessingService()
        service.start_worker()

        return count
