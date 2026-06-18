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
        if not ProcessingService._is_running:
            self.start_worker()

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
        def normalize_name(s: str) -> str:
            return s.lower().strip().replace("_", " ").replace("-", " ")
            
        project_classes_norm = [normalize_name(c) for c in project_classes]
        idx = ModelService._find_best_project_class_idx(name, project_classes_norm)
        if idx is not None:
            return idx
            
        lower_name = name.lower()
        for i, c in enumerate(project_classes):
            if c.lower() == lower_name:
                return i
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

            model_name = getattr(queue_item, "model_name", "nvidia/segformer-b3-finetuned-ade-512-512")
            print(f"[ProcessingService] Image {image.id} processing using model: {model_name}")
            
            if model_name == "nvidia/LocateAnything-3B":
                # VLM Bounding Box Grounding branch
                final_annotations_to_add = []
                all_confidences = []
                boxes = ModelService.generate_locateanything_boxes(image.absolute_path, project_classes)
                for box_item in boxes:
                    class_name_temp = box_item["class"]
                    bbox = box_item["bbox"]
                    conf = box_item.get("confidence", 0.8)
                    x, y, w, h = bbox
                    
                    # Call ModelService to get precise pixel mask instead of coarse polygon
                    polygon = ModelService.extract_pixel_mask(image.absolute_path, [x, y, w, h])
                    if not polygon:
                        polygon = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                    
                    final_annotations_to_add.append(
                        Annotation(
                            image_id=image.id,
                            class_name=class_name_temp,
                            model_source="LocateAnything-3B",
                            confidence=conf,
                            segmentation_json=json.dumps(polygon),
                            bbox_json=json.dumps({
                                "bbox": [x, y, w, h],
                                "area": w * h,
                                "alt_class": class_name_temp,
                                "agreement": conf,
                                "needs_attention": conf < settings.CONFIDENCE_UNKNOWN_THRESHOLD,
                            })
                        )
                    )
                    all_confidences.append(conf)

                # Create dummy maps for LocateAnything
                label_map = np.zeros((orig_h, orig_w), dtype=np.int32)
                confidence_map = np.zeros((orig_h, orig_w), dtype=np.float32)
                for ann in final_annotations_to_add:
                    class_idx = self._class_index(project_classes, ann.class_name)
                    if class_idx >= 0:
                        pts = np.array(json.loads(ann.segmentation_json), np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(label_map, [pts], class_idx)
                        cv2.fillPoly(confidence_map, [pts], ann.confidence)
                        
                avg_conf = float(np.mean(confidence_map[confidence_map > 0])) if np.any(confidence_map > 0) else 0.5
                audit_block = (
                    f"**AERIAL PIPELINE AUDIT**\n"
                    f"- Mode: LocateAnything-3B (VLM Grounding)\n"
                    f"- Bounding boxes generated directly from text prompt.\n"
                )
                feedback_notes = []

            else:
                # Dense pixel semantic segmentation pipeline (SegFormer)
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

                # ---------- Edge-Aware Boundary Refinement (Guided-Filter CRF) ----------
                # Instead of crude medianBlur, refine the probability map using the
                # original image's edges as guidance, then re-derive the label map.
                if orig_img is not None:
                    guide = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
                    num_classes_fused = p_fused.shape[2]
                    refined_probs = np.zeros_like(p_fused)
                    try:
                        for ch in range(num_classes_fused):
                            refined_probs[:, :, ch] = cv2.ximgproc.guidedFilter(
                                guide, p_fused[:, :, ch], radius=8, eps=1e-4
                            )
                    except AttributeError:
                        # Fallback if ximgproc not available: Strong Gaussian blur to eliminate 8x8 blocky interpolation artifacts
                        for ch in range(num_classes_fused):
                            prob_u8 = np.clip(p_fused[:, :, ch] * 255, 0, 255).astype(np.uint8)
                            # A 21x21 Gaussian blur completely smooths out the boxy artifacts
                            filtered = cv2.GaussianBlur(prob_u8, (21, 21), 0)
                            refined_probs[:, :, ch] = filtered.astype(np.float32) / 255.0

                    # Re-normalize after filtering
                    sum_refined = np.sum(refined_probs, axis=-1, keepdims=True)
                    sum_refined = np.maximum(sum_refined, 1e-6)
                    refined_probs = refined_probs / sum_refined

                    label_map = np.argmax(refined_probs, axis=-1).astype(np.int32)
                    confidence_map = np.max(refined_probs, axis=-1)
                    p_fused = refined_probs  # use refined probs for downstream

                # Removed SAM superpixel fallback which was creating 30x30 grid boxes

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

                # ---------- Class-Aware Small-Region Handling ----------
                # Use class-specific minimum area thresholds and merge small regions
                # into their most common neighboring class instead of deleting them.
                MIN_AREA_BY_CLASS = {
                    vehicle_idx: 30,      # vehicles are genuinely small in aerial views
                    self._class_index(project_classes, "shadow"): 50,
                }
                # Default minimums for common classes
                building_idx_temp = self._class_index(project_classes, "building")
                if building_idx_temp >= 0:
                    MIN_AREA_BY_CLASS[building_idx_temp] = 500
                for name in ("road", "sidewalk", "bare_ground", "tree_cover", "water_body"):
                    idx = self._class_index(project_classes, name)
                    if idx >= 0:
                        MIN_AREA_BY_CLASS.setdefault(idx, 200)
                DEFAULT_MIN_AREA = 150

                # Apply light median blur (kernel=3 instead of 5 for sharper edges)
                label_map = cv2.medianBlur(label_map.astype(np.uint8), 3)
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(label_map, connectivity=8)
                shadow_idx = self._class_index(project_classes, "shadow")

                for label_id in range(1, num_labels):
                    area = stats[label_id, cv2.CC_STAT_AREA]
                    region_class = int(np.median(label_map[labels == label_id]))
                    min_area = MIN_AREA_BY_CLASS.get(region_class, DEFAULT_MIN_AREA)

                    if area < min_area:
                        # Merge into the most common neighboring class instead of deleting
                        region_mask_small = labels == label_id
                        # Dilate the region to find its neighbors
                        dilated = cv2.dilate(region_mask_small.astype(np.uint8), np.ones((5, 5), np.uint8))
                        neighbor_mask = (dilated == 1) & (~region_mask_small)
                        if np.any(neighbor_mask):
                            neighbor_labels = label_map[neighbor_mask]
                            most_common_neighbor = np.bincount(neighbor_labels).argmax()
                            label_map[region_mask_small] = most_common_neighbor
                        # else: keep as-is (isolated regions)

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

                        if len(contour) < 3:
                            continue

                        polygon = [[float(point[0][0]), float(point[0][1])] for point in contour]
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

            # --- End of processing branch ---

            class_stats = {}
            for annotation in final_annotations_to_add:
                class_stats[annotation.class_name] = class_stats.get(annotation.class_name, 0) + 1

            # Gather class colors from project definition for overlay visualization
            class_colors = [
                project_class.color
                for project_class in image.project.classes
                if project_class.name.lower() != "unknown"
            ] or [None] * len(project_classes)

            SegmentationArtifactService.save_mask_overlay(
                image.project_id,
                image,
                label_map.astype(np.uint8),
                project_classes,
                class_colors=class_colors,
            )
            SegmentationArtifactService.save_confidence_map(image.project_id, image, confidence_map)

            avg_conf = float(np.mean(confidence_map))
            
            if model_name != "nvidia/LocateAnything-3B":
                audit_block = (
                    f"**AERIAL PIPELINE AUDIT**\n"
                    f"- Mode: {'SegFormer-b3 (fp16, multi-scale TTA)' if ModelService.is_real_mode_active() else 'Simulation'}\n"
                    f"- Tiling: {settings.TILE_SIZE}x{settings.TILE_SIZE}, overlap {settings.TILE_OVERLAP * 100}%\n"
                    f"- Tiles Processed: {len(tiles)}\n"
                    f"- Multi-scale inference: 3 scales × 2 orientations = 6 forward passes\n"
                    f"- Boundary refinement: Guided-filter CRF + SAM superpixel regions\n"
                    f"- Small-region handling: Class-aware thresholds + neighbor merging\n"
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
    def enqueue_all(db: Session, project_id: int, model_name: str = "nvidia/segformer-b3-finetuned-ade-512-512") -> int:
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

        if not images:
            return 0

        image_ids = [img.id for img in images]
        
        # Get all existing queue items in one query
        existing_items = db.query(ProcessingQueue).filter(ProcessingQueue.image_id.in_(image_ids)).all()
        existing_map = {item.image_id: item for item in existing_items}

        new_queue_items = []
        count = 0

        for image in images:
            existing = existing_map.get(image.id)
            if not existing:
                new_queue_items.append(ProcessingQueue(image_id=image.id, model_name=model_name))
                count += 1
            elif existing.status in ["completed", "failed"]:
                existing.status = "pending"
                existing.attempt_number = 1
                existing.model_name = model_name
                count += 1
            elif existing.status == "pending":
                existing.model_name = model_name

            image.status = "pending"

        if new_queue_items:
            db.bulk_save_objects(new_queue_items)

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            # If a race condition still somehow happens, ignore it since it means they are already in the queue
            pass

        service = ProcessingService()
        service.start_worker()

        return count
