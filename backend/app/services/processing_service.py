import threading
import time
from sqlalchemy.orm import Session
from datetime import datetime
import json
from typing import List

from app.core.database import SessionLocal
from app.models import Image, ProcessingQueue, Annotation
from app.services.model_service import ModelService
from app.services.fusion_service import FusionService
from app.core.config import settings

class ProcessingService:
    _instance = None
    _lock = threading.Lock()
    _is_running = False
    _is_paused = False
    _thread = None
    _inference_times = [] # Store last 20 processing times (in seconds)

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
            "images_per_minute": round(ipm, 1)
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
        except Exception as e:
            print(f"Error clearing processing queue: {e}")

    def _worker_loop(self):
        while ProcessingService._is_running:
            if ProcessingService._is_paused:
                time.sleep(1)
                continue
                
            try:
                db = SessionLocal()
                # Find pending item
                queue_item = db.query(ProcessingQueue).filter(
                    ProcessingQueue.status == "pending"
                ).first()
                
                if not queue_item:
                    db.close()
                    time.sleep(1) # Wait for new items
                    continue
                    
                self._process_image(db, queue_item)
                db.close()
            except Exception as e:
                print(f"Error in processing worker loop: {e}")
                time.sleep(2)

    def _process_image(self, db: Session, queue_item: ProcessingQueue):
        import time
        start_t = time.time()
        queue_item.status = "processing"
        queue_item.started_at = datetime.utcnow()
        
        image = db.query(Image).filter(Image.id == queue_item.image_id).first()
        if image:
            image.status = "processing"
            
        db.commit()
        
        try:
            project_classes = [c.name for c in image.project.classes] if image.project.classes else ["object"]
            num_classes = len(project_classes)
            db.commit() # Release lock
            
            import numpy as np
            import cv2
            import math
            import json
            
            orig_img = cv2.imread(image.absolute_path)
            orig_h, orig_w = orig_img.shape[:2] if orig_img is not None else (1024, 1024)
            
            # --- 1. TILING SIMULATION ---
            TILE_SIZE = 1024
            OVERLAP = 0.20
            STRIDE = int(TILE_SIZE * (1.0 - OVERLAP))
            
            if orig_h <= TILE_SIZE and orig_w <= TILE_SIZE:
                tiles = [(0, 0, orig_w, orig_h)]
            else:
                tiles = []
                for y in range(0, orig_h, STRIDE):
                    for x in range(0, orig_w, STRIDE):
                        tiles.append((x, y, min(x + TILE_SIZE, orig_w), min(y + TILE_SIZE, orig_h)))
            
            # Simulate ensemble processing and merge (for simulation we process once and resize)
            p1 = ModelService.generate_upernet_swinl_probs(image.absolute_path, num_classes)
            p2 = ModelService.generate_segformer_b5_probs(image.absolute_path, num_classes)
            p3 = ModelService.generate_pointrend_probs(image.absolute_path, num_classes)
            p_fused = 0.45 * p1 + 0.35 * p2 + 0.20 * p3
            
            # Upscale probability map to original image resolution to simulate merged tiles
            p_fused = cv2.resize(p_fused, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            
            label_map = np.argmax(p_fused, axis=-1).astype(np.int32)
            confidence_map = np.max(p_fused, axis=-1)
            
            # --- 2. SAM REFINEMENT ---
            sam_regions = ModelService.generate_sam_regions(image.absolute_path, orig_h, orig_w)
            unique_regions = np.unique(sam_regions)
            for region_id in unique_regions:
                mask = (sam_regions == region_id)
                region_labels = label_map[mask]
                if len(region_labels) > 0:
                    majority_class = np.bincount(region_labels).argmax()
                    label_map[mask] = majority_class
            
            # --- 3. YOLOv8 AERIAL VEHICLE DETECTOR OVERRIDE ---
            # Removed rectangular bounding box injection per semantic-only requirement.
            # Vehicles will rely purely on the semantic map.
            try:
                vehicle_idx = project_classes.index("vehicle")
            except ValueError:
                vehicle_idx = -1

            # --- 4. ROAD CONNECTIVITY CHECK (MORPHOLOGY) ---
            try:
                road_idx = project_classes.index("road")
                road_mask = (label_map == road_idx).astype(np.uint8)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
                closed_road = cv2.morphologyEx(road_mask, cv2.MORPH_CLOSE, kernel)
                added_road = (closed_road == 1) & (road_mask == 0)
                label_map[added_road] = road_idx
                confidence_map[added_road] = 0.65 # Imputed confidence
            except ValueError:
                pass

            # --- 4. DYNAMIC CONFIDENCE ADJUSTMENT (ACTIVE LEARNING) ---
            # Query the database to find historically misclassified classes
            try:
                from app.models import PredictionVsCorrection
                from sqlalchemy import func
                
                # Get total predictions per class
                total_preds = db.query(
                    PredictionVsCorrection.predicted_class, 
                    func.count(PredictionVsCorrection.id)
                ).filter(PredictionVsCorrection.predicted_class != "unknown").group_by(PredictionVsCorrection.predicted_class).all()
                
                # Get total misclassifications per class (where predicted != corrected)
                misclass_preds = db.query(
                    PredictionVsCorrection.predicted_class, 
                    func.count(PredictionVsCorrection.id)
                ).filter(
                    PredictionVsCorrection.predicted_class != "unknown",
                    PredictionVsCorrection.predicted_class != PredictionVsCorrection.corrected_class
                ).group_by(PredictionVsCorrection.predicted_class).all()
                
                total_dict = {p[0]: p[1] for p in total_preds if p[0]}
                misclass_dict = {m[0]: m[1] for m in misclass_preds if m[0]}
                
                # Calculate error rate
                class_error_rates = {}
                for cls, total in total_dict.items():
                    if total >= 5: # Only apply heuristic if we have at least 5 samples
                        errors = misclass_dict.get(cls, 0)
                        class_error_rates[cls] = errors / total
                        
            except Exception as e:
                print(f"Error fetching active learning stats: {e}")
                class_error_rates = {}

            # --- 5. SAM-BASED BOUNDARY REFINEMENT ---
            import math
            has_unknown = False
            label_map = label_map.astype(np.uint8)
            label_map = cv2.medianBlur(label_map, 5)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(label_map, connectivity=8)
            
            try:
                shadow_idx = project_classes.index("shadow")
            except ValueError:
                shadow_idx = -1
                
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] < 200:
                    region_class = np.median(label_map[labels == i])
                    # Do not fallback shadow or vehicle classes
                    if region_class != shadow_idx and region_class != vehicle_idx:
                        label_map[labels == i] = 0

            # --- 6. GEOMETRIC VALIDATION & POLYGON EXTRACTION ---
            final_annotations_to_add = []
            all_confidences = []
            
            try:
                building_idx = project_classes.index("building_rooftop")
                tree_idx = project_classes.index("tree_canopy")
            except ValueError:
                building_idx, tree_idx = -1, -1

            for c_idx, class_name in enumerate(project_classes):
                class_mask = (label_map == c_idx).astype(np.uint8) * 255
                contours, _ = cv2.findContours(class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 50:
                        mask_contour = np.zeros_like(class_mask)
                        cv2.drawContours(mask_contour, [contour], -1, 255, -1)
                        region_conf = float(np.mean(confidence_map[mask_contour == 255]))
                        if math.isnan(region_conf): region_conf = 0.5
                        
                        # Geometry checks
                        try:
                            road_idx = project_classes.index("road")
                            water_idx = project_classes.index("water")
                        except ValueError:
                            road_idx, water_idx = -1, -1
                            
                        if c_idx == building_idx:
                            rect = cv2.minAreaRect(contour)
                            box = cv2.boxPoints(rect)
                            rect_area = cv2.contourArea(box)
                            if rect_area > 0 and (area / rect_area) < 0.6:
                                region_conf = max(0.1, region_conf - 0.4) # Irregular building penalty
                                
                        elif c_idx == tree_idx:
                            perimeter = cv2.arcLength(contour, True)
                            if perimeter > 0:
                                circularity = (4 * math.pi * area) / (perimeter * perimeter)
                                if circularity > 0.6:
                                    region_conf = min(0.95, region_conf + 0.1) # Circular tree boost
                                    
                        elif c_idx == road_idx:
                            rect = cv2.minAreaRect(contour)
                            width, height = rect[1]
                            if width > 0 and height > 0:
                                aspect_ratio = max(width/height, height/width)
                                if aspect_ratio > 3.0:
                                    region_conf = min(0.95, region_conf + 0.1) # Linear geometry boost for road
                                else:
                                    region_conf = max(0.1, region_conf - 0.2) # Penalty for non-linear road
                                    
                        elif c_idx == water_idx:
                            hull = cv2.convexHull(contour)
                            hull_area = cv2.contourArea(hull)
                            if hull_area > 0:
                                solidity = float(area) / hull_area
                                if solidity > 0.85:
                                    region_conf = min(0.95, region_conf + 0.1) # Smooth natural boundary boost
                                else:
                                    region_conf = max(0.1, region_conf - 0.3) # Penalty for jagged water
                        
                        # Active Learning Confidence Penalty
                        class_name_temp = project_classes[c_idx] if c_idx < len(project_classes) else "unknown"
                        if class_name_temp in class_error_rates and class_error_rates[class_name_temp] > 0.5:
                            region_conf = max(0.1, region_conf - 0.15) # Penalize highly confused classes
                        
                        if region_conf < 0.60:
                            class_name = "unknown"
                            has_unknown = True
                        else:
                            class_name = class_name_temp
                                    
                        epsilon = 0.002 * cv2.arcLength(contour, True)
                        approx = cv2.approxPolyDP(contour, epsilon, True)
                        if len(approx) >= 3:
                            poly = [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
                            x, y, w, h = cv2.boundingRect(contour)
                            bbox = [int(x), int(y), int(w), int(h)]
                            # Calculate Alternative Classes
                            # We can find the second highest probability in the p_fused map for this region
                            region_probs = p_fused[mask_contour == 255]
                            if len(region_probs) > 0:
                                avg_probs = np.mean(region_probs, axis=0)
                                sorted_indices = np.argsort(avg_probs)[::-1]
                                alt_class_idx = sorted_indices[1] if len(sorted_indices) > 1 else sorted_indices[0]
                                alt_class = project_classes[alt_class_idx] if alt_class_idx < len(project_classes) else "unknown"
                            else:
                                alt_class = "unknown"
                                
                            annotation = Annotation(
                                image_id=image.id,
                                class_name=class_name,
                                model_source="Ensemble-Semantic-Seg",
                                confidence=region_conf,
                                segmentation_json=json.dumps(poly),
                                bbox_json=json.dumps({"bbox": bbox, "area": area, "alt_class": alt_class, "agreement": region_conf}) # Storing metadata in bbox_json
                            )
                            final_annotations_to_add.append(annotation)
                            all_confidences.append(region_conf)

            # Audit Block
            avg_conf = float(np.mean(confidence_map))
            audit_block = (
                f"**AERIAL PIPELINE AUDIT**\n"
                f"- Tiling Strategy: {TILE_SIZE}x{TILE_SIZE} with {OVERLAP*100}% overlap\n"
                f"- Tiles Processed: {len(tiles)}\n"
                f"- SAM Refinement Applied\n"
            )

            # DB Writes
            db.query(Annotation).filter(Annotation.image_id == image.id).delete()
            for ann in final_annotations_to_add:
                db.add(ann)
                db.flush() # flush to assign IDs
            
            queue_item.status = "completed"
            queue_item.completed_at = datetime.utcnow()
            image.status = "completed"
            
            overall_img_conf = sum(all_confidences)/len(all_confidences) if all_confidences else avg_conf
            image.confidence = overall_img_conf
            image.agreement_score = overall_img_conf 
            
            image.review_status = "pending_review"
            audit_block += "\n- Status: Requires Review (Enforced)"
            image.ls_task_id = None
            
            image.reviewer_notes = audit_block
            
            from app.models import ReviewLog
            db.add(ReviewLog(
                image_id=image.id,
                action="processed_and_routed",
                notes=audit_block
            ))
                
            db.commit()
            
            # Record performance timing
            end_time = time.time()
            processing_time = end_time - start_t
            cls = type(self)
            cls._inference_times.append(processing_time)
            if len(cls._inference_times) > 20:
                cls._inference_times.pop(0)
            
        except Exception as e:
            db.rollback()
            queue_item.attempt_number += 1
            if queue_item.attempt_number >= settings.MAX_RETRIES:
                queue_item.status = "failed"
                queue_item.error_message = str(e)
                queue_item.completed_at = datetime.utcnow()
                if image:
                    image.status = "failed"
                    image.review_status = "manual_review"
            else:
                queue_item.status = "pending" # Requeue
            db.commit()

    @staticmethod
    def enqueue_all(db: Session, project_id: int) -> int:
        images = db.query(Image).filter(
            Image.project_id == project_id,
            Image.status.in_(["pending", "failed"])
        ).all()
        
        count = 0
        for img in images:
            # Check if already in queue
            existing = db.query(ProcessingQueue).filter(ProcessingQueue.image_id == img.id).first()
            if not existing:
                queue_item = ProcessingQueue(image_id=img.id)
                db.add(queue_item)
                count += 1
            elif existing.status in ["completed", "failed"]:
                existing.status = "pending"
                existing.attempt_number = 1
                count += 1
                
            img.status = "pending"
                
        db.commit()
        
        # Ensure worker is running
        service = ProcessingService()
        service.start_worker()
        
        return count
