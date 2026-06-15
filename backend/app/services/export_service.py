import json
import os
import zipfile
import shutil
from datetime import datetime
import numpy as np
import cv2
from sqlalchemy.orm import Session
from app.models import Project, Image, Annotation, ReviewLog, ProcessingQueue

class ExportService:
    @staticmethod
    def export_dataset(db: Session, project_id: int, output_dir: str, mode: str = "reviewed") -> str:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")

        # Determine which images to export
        if mode == "human_corrected":
            valid_statuses = ["human_corrected"]
        elif mode == "reviewed":
            valid_statuses = ["reviewed", "accepted", "human_corrected"]
        else:
            valid_statuses = ["reviewed", "accepted", "human_corrected"]
            
        images = db.query(Image).filter(Image.project_id == project_id, Image.review_status.in_(valid_statuses)).all()
        
        # Create staging dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        staging_dir = os.path.join(output_dir, f"export_{project_id}_{mode}_{timestamp}")
        os.makedirs(staging_dir, exist_ok=True)
        
        # We need subdirectories for various formats
        img_dir = os.path.join(staging_dir, "images")
        mask_dir = os.path.join(staging_dir, "masks")
        conf_dir = os.path.join(staging_dir, "confidence")
        
        coco_dir = os.path.join(staging_dir, "coco_segmentation")
        d2_dir = os.path.join(staging_dir, "detectron2")
        mmdet_dir = os.path.join(staging_dir, "mmdetection")
        segformer_dir = os.path.join(staging_dir, "segformer")
        m2f_dir = os.path.join(staging_dir, "mask2former")
        geojson_dir = os.path.join(staging_dir, "geojson")
        shapefile_dir = os.path.join(staging_dir, "shapefile")
        
        for d in [img_dir, mask_dir, conf_dir, coco_dir, d2_dir, mmdet_dir, segformer_dir, m2f_dir, geojson_dir, shapefile_dir]:
            os.makedirs(d, exist_ok=True)
            
        with open(os.path.join(staging_dir, "README.md"), "w") as f:
            f.write("# Dataset Export\n\nThis dataset contains human-reviewed annotations structured for various deep learning frameworks.")

        class_map = {cls.name: idx for idx, cls in enumerate(project.classes)}
        
        review_progress = []
        audit_lines = []
        class_stats = {name: 0 for name in class_map.keys()}
        
        for img in images:
            # Save original image copy
            shutil.copy2(img.absolute_path, os.path.join(img_dir, img.filename))
            
            # Generate label_map.png
            orig_img = cv2.imread(img.absolute_path)
            h, w = orig_img.shape[:2] if orig_img is not None else (1024, 1024)
            label_map = np.zeros((h, w), dtype=np.uint8)
            
            # Generate confidence.npy
            conf_map = np.zeros((h, w), dtype=np.float32)
            
            for ann in img.annotations:
                if not ann.segmentation_json:
                    continue
                poly = json.loads(ann.segmentation_json)
                if len(poly) < 3: continue
                
                cls_idx = class_map.get(ann.class_name, 0)
                class_stats[ann.class_name] = class_stats.get(ann.class_name, 0) + 1
                
                pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(label_map, [pts], cls_idx)
                cv2.fillPoly(conf_map, [pts], float(ann.confidence))
                
            base_name = os.path.splitext(img.filename)[0]
            cv2.imwrite(os.path.join(mask_dir, f"{base_name}_label_map.png"), label_map)
            np.save(os.path.join(conf_dir, f"{base_name}_confidence.npy"), conf_map)
            
            # Review Progress mapping
            review_progress.append({
                "image_id": img.id,
                "filename": img.filename,
                "review_status": img.review_status,
                "reviewer": img.reviewer,
                "last_viewed": img.last_viewed.isoformat() if img.last_viewed else None,
                "correction_count": img.correction_count
            })
            
            if img.reviewer_notes:
                audit_lines.append(f"--- Image {img.filename} ---")
                audit_lines.append(img.reviewer_notes)
                
        # Export remaining queue status
        queue_items = db.query(ProcessingQueue).join(Image).filter(Image.project_id == project_id, ProcessingQueue.status == "pending").all()
        queue_data = [{"image_id": q.image_id, "filename": q.image.filename} for q in queue_items]
        
        # Project State
        project_state = {
            "name": project.name,
            "classes": [{"id": idx, "name": name} for name, idx in class_map.items()],
            "exported_images_count": len(images)
        }
        
        with open(os.path.join(staging_dir, "review_queue.json"), "w") as f:
            json.dump(queue_data, f, indent=2)
            
        with open(os.path.join(staging_dir, "review_progress.json"), "w") as f:
            json.dump(review_progress, f, indent=2)
            
        with open(os.path.join(staging_dir, "class_statistics.json"), "w") as f:
            json.dump(class_stats, f, indent=2)
            
        with open(os.path.join(staging_dir, "project_state.json"), "w") as f:
            json.dump(project_state, f, indent=2)
            
        with open(os.path.join(staging_dir, "audit_log.txt"), "w") as f:
            f.write("\n".join(audit_lines))
            
        # Zip it up
        zip_path = f"{staging_dir}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(staging_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, staging_dir)
                    zipf.write(file_path, arcname)
                    
        # Cleanup staging
        shutil.rmtree(staging_dir)
        
        return zip_path
