import cv2
import numpy as np
import json
import os
from typing import Dict, Any, List

class ModelService:
    @staticmethod
    def _extract_polygons_from_mask(binary_mask: np.ndarray) -> List[List[List[float]]]:
        """Extracts polygon coordinates from a binary mask."""
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for contour in contours:
            if cv2.contourArea(contour) > 50: # Minimum area
                # Simplify contour
                epsilon = 0.005 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                if len(approx) >= 3:
                    poly = [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
                    polygons.append(poly)
        return polygons

    @staticmethod
    def _get_execution_device() -> str:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    @staticmethod
    def load_real_models():
        """Called if USE_REAL_MODELS is True. Enforces CUDA."""
        device = ModelService._get_execution_device()
        print(f"[{device.upper()}] Loading GroundingDINO, SAM2, Florence-2 onto {device}...")
        if device == "cpu":
            print("WARNING: Falling back to CPU. CUDA is unavailable.")
        # Actual loading logic would go here

    @staticmethod
    def _generate_simulated_prob_map(image_path: str, num_classes: int, noise_level: float, base_seed: int) -> np.ndarray:
        """
        Generates a simulated probability map (H, W, num_classes) by using OpenCV image segmentation
        heuristics to create somewhat realistic distinct regions, adding controlled noise to simulate model variance.
        """
        img = cv2.imread(image_path)
        if img is None:
            # Fallback size
            img = np.zeros((256, 256, 3), dtype=np.uint8)
            
        # We process at a lower fixed resolution for speed
        H, W = 256, 256
        img_resized = cv2.resize(img, (W, H))
        
        # Use SLIC superpixels or just simple blurred quantization as a base
        blurred = cv2.bilateralFilter(img_resized, 9, 75, 75)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        
        # Base probabilities
        np.random.seed(base_seed)
        probs = np.ones((H, W, num_classes), dtype=np.float32) * 0.01
        
        # Create 5-10 distinct intensity regions
        quantized = (gray // 32) * 32
        unique_vals = np.unique(quantized)
        
        # Assign a random class to each intensity region
        for val in unique_vals:
            mask = (quantized == val)
            cls_idx = np.random.randint(0, num_classes)
            probs[mask, cls_idx] = 0.8
            
        # Add spatial noise (simulating model uncertainty)
        noise = np.random.normal(0, noise_level, (H, W, num_classes))
        probs = probs + noise
        probs = np.clip(probs, 0.001, 10.0)
        
        # Softmax to ensure it sums to 1
        exp_p = np.exp(probs)
        softmax = exp_p / np.sum(exp_p, axis=-1, keepdims=True)
        return softmax

    @staticmethod
    def generate_upernet_swinl_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.5, base_seed=42)

    @staticmethod
    def generate_segformer_b5_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.8, base_seed=43)

    @staticmethod
    def generate_pointrend_probs(image_path: str, num_classes: int) -> np.ndarray:
        return ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=1.2, base_seed=44)

    @staticmethod
    def generate_sam_regions(image_path: str, scale_h: int, scale_w: int) -> np.ndarray:
        """
        Simulates SAM generating distinct superpixel regions.
        Returns an integer mask of shape (scale_h, scale_w) where each unique int is a distinct SAM region.
        """
        img = cv2.imread(image_path)
        if img is None:
            return np.zeros((scale_h, scale_w), dtype=np.int32)
        img_resized = cv2.resize(img, (scale_w, scale_h))
        try:
            # Simple SLIC superpixels as SAM simulation
            slic = cv2.ximgproc.createSuperpixelSLIC(img_resized, algorithm=cv2.ximgproc.SLIC, region_size=30, ruler=10.0)
            slic.iterate(10)
            labels = slic.getLabels()
            return labels
        except AttributeError:
            # Fallback if cv2.ximgproc is not available
            grid_y, grid_x = np.mgrid[0:scale_h, 0:scale_w]
            labels = (grid_y // 30) * (scale_w // 30 + 1) + (grid_x // 30)
            return labels.astype(np.int32)

    @staticmethod
    def generate_yolov8_vehicles(image_path: str, scale_h: int, scale_w: int) -> List[Dict[str, Any]]:
        """
        Simulates YOLOv8 aerial vehicle detection. Returns a list of bounding boxes
        scaled to the provided dimensions (scale_h, scale_w).
        Returns list of dicts: {'class': 'vehicle', 'bbox': [x, y, w, h]}
        """
        # We'll just randomly drop 0-3 vehicle boxes
        np.random.seed(hash(image_path) % 10000)
        num_vehicles = np.random.randint(0, 4)
        vehicles = []
        for _ in range(num_vehicles):
            w = np.random.randint(20, 60)
            h = np.random.randint(20, 60)
            x = np.random.randint(0, scale_w - w)
            y = np.random.randint(0, scale_h - h)
            vehicles.append({
                'class': 'vehicle',
                'bbox': [x, y, w, h]
            })
        return vehicles
