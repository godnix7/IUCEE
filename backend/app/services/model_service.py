import cv2
import numpy as np
import json
import os
from typing import Dict, Any, List, Optional

# Maps ADE20K / general segmentation labels to the project's aerial ontology.
ADE_TO_AERIAL: Dict[str, str] = {
    "road": "road",
    "sidewalk": "sidewalk_path",
    "path": "sidewalk_path",
    "building": "building_rooftop",
    "house": "building_rooftop",
    "skyscraper": "building_rooftop",
    "grandstand": "building_rooftop",
    "parking lot": "parking_lot",
    "parking": "parking_lot",
    "car": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
    "van": "vehicle",
    "minibus": "vehicle",
    "bicycle": "vehicle",
    "motorcycle": "vehicle",
    "grass": "low_vegetation",
    "plant": "low_vegetation",
    "field": "low_vegetation",
    "flower": "low_vegetation",
    "tree": "tree_canopy",
    "palm": "tree_canopy",
    "water": "water",
    "river": "water",
    "sea": "water",
    "lake": "water",
    "swimming pool": "water",
    "pool": "water",
    "dirt": "bare_ground",
    "sand": "bare_ground",
    "earth": "bare_ground",
    "ground": "bare_ground",
    "land": "bare_ground",
    "runway": "road",
    "bridge": "road",
    "construction": "construction",
    "scaffolding": "construction",
}


class ModelService:
    _real_models_loaded = False
    _device: str = "cpu"
    _segformer_processor = None
    _segformer_model = None

    @staticmethod
    def _extract_polygons_from_mask(binary_mask: np.ndarray) -> List[List[List[float]]]:
        """Extracts polygon coordinates from a binary mask."""
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for contour in contours:
            if cv2.contourArea(contour) > 50:
                epsilon = 0.005 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                if len(approx) >= 3:
                    poly = [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
                    polygons.append(poly)
        return polygons

    @staticmethod
    def _get_torch():
        try:
            import torch
            return torch
        except Exception as exc:
            print(f"[ModelService] PyTorch unavailable: {exc}")
            return None

    @staticmethod
    def _get_execution_device() -> str:
        torch = ModelService._get_torch()
        if torch and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @staticmethod
    def is_real_mode_active() -> bool:
        from app.core.config import settings
        return settings.USE_REAL_MODELS and ModelService._real_models_loaded

    @staticmethod
    def load_real_models():
        """Load SegFormer for GPU semantic segmentation when enabled."""
        from app.core.config import settings
        if not settings.USE_REAL_MODELS:
            print("[ModelService] USE_REAL_MODELS=false, using simulation pipeline.")
            return

        torch = ModelService._get_torch()
        if torch is None:
            print("[ModelService] WARNING: PyTorch not available. Falling back to simulation.")
            return

        device = ModelService._get_execution_device()
        ModelService._device = device
        print(f"[{device.upper()}] Loading SegFormer (ADE20K) onto {device}...")

        try:
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

            model_id = "nvidia/segformer-b0-finetuned-ade-512-512"
            ModelService._segformer_processor = AutoImageProcessor.from_pretrained(model_id)
            ModelService._segformer_model = AutoModelForSemanticSegmentation.from_pretrained(model_id)
            ModelService._segformer_model.to(device)
            ModelService._segformer_model.eval()
            ModelService._real_models_loaded = True
            print(f"[ModelService] SegFormer loaded successfully on {device}.")
        except Exception as exc:
            ModelService._real_models_loaded = False
            print(f"[ModelService] Failed to load SegFormer: {exc}")
            print("[ModelService] Falling back to simulation pipeline.")

    @staticmethod
    def _generate_simulated_prob_map(image_path: str, num_classes: int, noise_level: float, base_seed: int) -> np.ndarray:
        img = cv2.imread(image_path)
        if img is None:
            img = np.zeros((256, 256, 3), dtype=np.uint8)

        H, W = 256, 256
        img_resized = cv2.resize(img, (W, H))

        blurred = cv2.bilateralFilter(img_resized, 9, 75, 75)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

        np.random.seed(base_seed)
        probs = np.ones((H, W, num_classes), dtype=np.float32) * 0.01

        quantized = (gray // 32) * 32
        unique_vals = np.unique(quantized)

        for val in unique_vals:
            mask = (quantized == val)
            cls_idx = np.random.randint(0, num_classes)
            probs[mask, cls_idx] = 0.8

        noise = np.random.normal(0, noise_level, (H, W, num_classes))
        probs = probs + noise
        probs = np.clip(probs, 0.001, 10.0)

        exp_p = np.exp(probs)
        softmax = exp_p / np.sum(exp_p, axis=-1, keepdims=True)
        return softmax

    @staticmethod
    def _map_ade_label_to_aerial(label: str) -> Optional[str]:
        normalized = label.lower().strip().replace("_", " ")
        if normalized in ADE_TO_AERIAL:
            return ADE_TO_AERIAL[normalized]
        for key, aerial in ADE_TO_AERIAL.items():
            if key in normalized or normalized in key:
                return aerial
        return None

    @staticmethod
    def _generate_real_prob_map(image_path: str, project_classes: List[str]) -> np.ndarray:
        """Run SegFormer on GPU/CPU and map ADE20K logits to project classes."""
        if not ModelService._real_models_loaded:
            raise RuntimeError("Real models are not loaded")

        torch = ModelService._get_torch()
        from PIL import Image as PILImage

        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        orig_h, orig_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(img_rgb)

        inputs = ModelService._segformer_processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(ModelService._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = ModelService._segformer_model(**inputs)
            logits = outputs.logits
            upsampled = torch.nn.functional.interpolate(
                logits,
                size=(orig_h, orig_w),
                mode="bilinear",
                align_corners=False,
            )
            probs_ade = torch.softmax(upsampled, dim=1).squeeze(0).cpu().numpy()

        num_classes = len(project_classes)
        class_to_idx = {name: idx for idx, name in enumerate(project_classes)}
        unknown_idx = class_to_idx.get("unknown", num_classes - 1)
        fused = np.full((orig_h, orig_w, num_classes), 1e-4, dtype=np.float32)

        id2label = ModelService._segformer_model.config.id2label
        for ade_idx in range(probs_ade.shape[0]):
            ade_label = id2label.get(ade_idx, id2label.get(str(ade_idx), ""))
            aerial_name = ModelService._map_ade_label_to_aerial(str(ade_label))
            if aerial_name and aerial_name in class_to_idx:
                target_idx = class_to_idx[aerial_name]
            else:
                target_idx = unknown_idx
            fused[:, :, target_idx] += probs_ade[ade_idx]

        fused = fused / np.sum(fused, axis=-1, keepdims=True)
        return fused.astype(np.float32)

    @staticmethod
    def generate_fused_probability_map(image_path: str, project_classes: List[str]) -> np.ndarray:
        """Primary entry point used by the processing pipeline."""
        num_classes = len(project_classes)
        if ModelService.is_real_mode_active():
            try:
                return ModelService._generate_real_prob_map(image_path, project_classes)
            except Exception as exc:
                print(f"[ModelService] Real inference failed, using simulation: {exc}")

        p1 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.5, base_seed=42)
        p2 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=0.8, base_seed=43)
        p3 = ModelService._generate_simulated_prob_map(image_path, num_classes, noise_level=1.2, base_seed=44)
        small_h, small_w = p1.shape[:2]

        img = cv2.imread(image_path)
        orig_h, orig_w = img.shape[:2] if img is not None else (small_h, small_w)
        fused_small = 0.45 * p1 + 0.35 * p2 + 0.20 * p3
        return cv2.resize(fused_small, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

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
        img = cv2.imread(image_path)
        if img is None:
            return np.zeros((scale_h, scale_w), dtype=np.int32)
        img_resized = cv2.resize(img, (scale_w, scale_h))
        try:
            slic = cv2.ximgproc.createSuperpixelSLIC(
                img_resized, algorithm=cv2.ximgproc.SLIC, region_size=30, ruler=10.0
            )
            slic.iterate(10)
            return slic.getLabels()
        except AttributeError:
            grid_y, grid_x = np.mgrid[0:scale_h, 0:scale_w]
            labels = (grid_y // 30) * (scale_w // 30 + 1) + (grid_x // 30)
            return labels.astype(np.int32)

    @staticmethod
    def generate_yolov8_vehicles(image_path: str, scale_h: int, scale_w: int) -> List[Dict[str, Any]]:
        np.random.seed(hash(image_path) % 10000)
        num_vehicles = np.random.randint(0, 4)
        vehicles = []
        for _ in range(num_vehicles):
            w = np.random.randint(20, 60)
            h = np.random.randint(20, 60)
            x = np.random.randint(0, max(1, scale_w - w))
            y = np.random.randint(0, max(1, scale_h - h))
            vehicles.append({"class": "vehicle", "bbox": [x, y, w, h]})
        return vehicles
