import cv2
import numpy as np
from sqlalchemy.orm import Session
from collections import Counter
from app.models import ReviewLog

class ValidationService:
    
    @staticmethod
    def get_geometry_features(polygon_pts):
        if not polygon_pts or len(polygon_pts) < 3:
            return {"area": 0, "perimeter": 0, "rectangularity": 0, "circularity": 0, "aspect_ratio": 1}
            
        pts = np.array([[pt["x"], pt["y"]] for pt in polygon_pts], dtype=np.int32)
        
        area = cv2.contourArea(pts)
        perimeter = cv2.arcLength(pts, True)
        
        if area == 0 or perimeter == 0:
            return {"area": 0, "perimeter": 0, "rectangularity": 0, "circularity": 0, "aspect_ratio": 1}
            
        # Rectangularity: Area / Bounding Rect Area
        rect = cv2.minAreaRect(pts)
        box = cv2.boxPoints(rect)
        box_area = cv2.contourArea(box)
        rectangularity = area / box_area if box_area > 0 else 0
        
        # Circularity (4*pi*area / perimeter^2) - high means round, low means irregular
        circularity = (4 * np.pi * area) / (perimeter * perimeter)
        
        # Aspect Ratio
        w, h = rect[1]
        if w == 0 or h == 0:
            aspect_ratio = 1
        else:
            aspect_ratio = max(w/h, h/w)
            
        return {
            "area": area,
            "perimeter": perimeter,
            "rectangularity": rectangularity,
            "circularity": circularity,
            "aspect_ratio": aspect_ratio
        }

    @staticmethod
    def validate_building(features: dict) -> bool:
        # Buildings should be roughly rectangular
        return features["rectangularity"] > 0.65

    @staticmethod
    def validate_tree(features: dict) -> bool:
        # Trees have irregular, non-rectangular canopies
        return features["rectangularity"] < 0.85 and features["circularity"] > 0.2

    @staticmethod
    def validate_road(features: dict) -> bool:
        # Roads should be highly linear
        return features["aspect_ratio"] > 3.0

    @staticmethod
    def validate_water(features: dict) -> bool:
        # Water is usually large and somewhat smooth
        return features["area"] > 1000

    @staticmethod
    def get_historical_penalty(db: Session, proposed_class: str) -> float:
        """
        Calculates how often the `proposed_class` was ACTUALLY wrong (Human corrected it to something else).
        Returns a penalty factor between 0.0 (never wrong) and 0.5 (often wrong).
        """
        # Count how many times proposed_class was predicted
        total_predictions = db.query(ReviewLog).filter(
            ReviewLog.action == "corrected",
            ReviewLog.predicted_class == proposed_class
        ).count()
        
        if total_predictions < 5:
            return 0.0 # Not enough data
            
        # Count how many times it was WRONG (actual_class != proposed_class)
        wrong_predictions = db.query(ReviewLog).filter(
            ReviewLog.action == "corrected",
            ReviewLog.predicted_class == proposed_class,
            ReviewLog.actual_class != proposed_class
        ).count()
        
        error_rate = wrong_predictions / total_predictions
        # Cap penalty at 0.3
        return min(error_rate, 0.3)

    @classmethod
    def process_and_validate(cls, db: Session, models_predictions: list, polygon_pts: list):
        """
        models_predictions: [{"model": "SAM2", "class": "Building", "confidence": 0.8}, ...]
        Returns: (final_class, final_confidence, status_flag)
        """
        # 1. Consensus
        classes = [p["class"] for p in models_predictions]
        counter = Counter(classes)
        modal_class, modal_count = counter.most_common(1)[0]
        
        # Calculate base confidence based on agreement + avg model conf
        agreement_ratio = modal_count / len(models_predictions)
        avg_conf = sum(p["confidence"] for p in models_predictions if p["class"] == modal_class) / modal_count
        
        raw_confidence = (agreement_ratio * 0.5) + (avg_conf * 0.5)
        
        # 2. Geometric Validation
        features = cls.get_geometry_features(polygon_pts)
        
        is_valid = True
        c_lower = modal_class.lower()
        if "building" in c_lower:
            is_valid = cls.validate_building(features)
        elif "tree" in c_lower or "vegetation" in c_lower:
            is_valid = cls.validate_tree(features)
        elif "road" in c_lower:
            is_valid = cls.validate_road(features)
        elif "water" in c_lower:
            is_valid = cls.validate_water(features)
            
        # 3. Penalize based on historical confusion
        penalty = cls.get_historical_penalty(db, modal_class)
        final_confidence = raw_confidence - penalty
        
        # 4. Check Mask-to-Box ratio Quality Rule
        if features["rectangularity"] > 0.95:
            is_valid = False
            # Massive penalty for saving a bounding box instead of a true mask
            final_confidence -= 0.5 
            
        if not is_valid:
            final_confidence -= 0.3 # Heavy penalty for failing geometry checks
            
        # 5. Apply Thresholds
        if features["rectangularity"] > 0.95:
            return "UNKNOWN", final_confidence, "Segmentation Failure"
            
        if final_confidence > 0.90:
            return modal_class, final_confidence, "Auto Assign"
        elif final_confidence >= 0.70:
            return modal_class, final_confidence, "Needs Review"
        else:
            return "UNKNOWN", final_confidence, "Low Confidence"
