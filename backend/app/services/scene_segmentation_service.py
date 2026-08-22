import os
import time
import math
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
import rasterio
import torch
from PIL import Image as PILImage
from shapely.geometry import box as shapely_box, MultiPolygon
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

from app.core.config import settings


# ADE20K (150 classes) -> UrbanSense class, matched by label-name substring so it is
# robust to exact index ordering.
_ADE_MAP = [
    (("building", "house", "skyscraper", "hovel", "tower", "wall"), "building"),
    (("road", "route", "runway"), "road"),
    (("sidewalk", "pavement"), "sidewalk"),
    (("tree", "palm"), "tree_cover"),
    (("grass",), "grass"),
    (("field", "farm"), "agriculture"),
    (("water", "sea", "river", "lake", "pool", "waterfall", "fountain"), "water"),
    (("earth", "ground", "dirt", "sand", "land", "hill", "mountain", "rock", "path"), "barren_land"),
    (("car", "truck", "bus", "van", "minibike", "motorbike", "bicycle", "boat", "train", "airplane"), "vehicle"),
    (("person",), "person"),
]

# RGB colors for the annotated overlay (aligns with the frontend CLASS_COLORS)
_CLASS_COLORS = {
    "building": (239, 68, 68), "road": (100, 116, 139), "sidewalk": (234, 179, 8),
    "tree_cover": (34, 197, 94), "grass": (132, 204, 22), "agriculture": (163, 230, 53),
    "water": (6, 182, 212), "barren_land": (249, 115, 22), "vehicle": (59, 130, 246),
    "person": (236, 72, 153),
}
_DEFAULT_COLOR = (148, 163, 184)


class SceneSegmentationService:
    """
    Semantic scene parsing for oblique / drone imagery using an ADE20K-trained SegFormer.
    Counterpart to AIService (LoveDA, nadir). Selected when analysis_mode == 'scene_segmentation'.
    Produces per-class coverage features + an annotated colour-mask overlay image.
    """
    _processor = None
    _model = None
    _label_to_class: Dict[int, str] = {}
    _device = "cuda" if torch.cuda.is_available() else "cpu"

    @classmethod
    def load_model(cls):
        if cls._model is None:
            name = settings.SCENE_SEG_MODEL
            print(f"[SceneSeg] Loading ADE20K model: {name} on {cls._device}")
            cls._processor = AutoImageProcessor.from_pretrained(name)
            cls._model = AutoModelForSemanticSegmentation.from_pretrained(name)
            cls._model.to(cls._device)
            cls._model.eval()
            # Precompute ADE label id -> UrbanSense class
            id2label = cls._model.config.id2label
            mapping = {}
            for cid, lname in id2label.items():
                ln = str(lname).lower()
                for keys, target in _ADE_MAP:
                    if any(k in ln for k in keys):
                        mapping[int(cid)] = target
                        break
            cls._label_to_class = mapping
            print(f"[SceneSeg] Model loaded; {len(mapping)} ADE classes mapped to UrbanSense classes.")

    @classmethod
    def run_scene_segmentation(
        cls,
        image_path: str,
        transform: Any,
        metadata: Dict[str, Any],
        annotated_out_path: Optional[str] = None,
        progress_callback=None,
    ) -> Tuple[List[dict], float, float, int, Dict[str, float]]:
        """Returns (features, avg_confidence, inference_time_sec, num_classes, class_coverage_pct)."""
        start = time.time()
        cls.load_model()
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        with rasterio.open(image_path) as src:
            if src.count < 3:
                raise ValueError(f"Scene segmentation requires 3 bands (RGB). Found {src.count}.")
            arr = np.transpose(src.read([1, 2, 3]), (1, 2, 0))
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        H, W = arr.shape[:2]
        if progress_callback:
            progress_callback(0, 1)

        with torch.inference_mode():
            inp = cls._processor(images=PILImage.fromarray(arr), return_tensors="pt").to(cls._device)
            out = cls._model(**inp)
        up = torch.nn.functional.interpolate(out.logits, size=(H, W), mode="bilinear", align_corners=False)
        probs = torch.softmax(up, dim=1)
        conf_map, seg = torch.max(probs, dim=1)
        seg = seg.squeeze(0).cpu().numpy()
        conf_map = conf_map.squeeze(0).cpu().numpy()

        # Aggregate ADE pixels into UrbanSense classes
        total = H * W
        class_pixels: Dict[str, np.ndarray] = {}
        for cid, target in cls._label_to_class.items():
            m = seg == cid
            if not m.any():
                continue
            class_pixels[target] = class_pixels.get(target, np.zeros((H, W), bool)) | m

        features: List[dict] = []
        coverage: Dict[str, float] = {}
        confs: List[float] = []
        for target, mask in class_pixels.items():
            px = int(mask.sum())
            if px < total * 0.002:  # drop specks < 0.2%
                continue
            pct = round(100.0 * px / total, 2)
            coverage[target] = pct
            cconf = float(conf_map[mask].mean())
            confs.append(cconf)
            ys, xs = np.where(mask)
            bbox = shapely_box(float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
            features.append({
                "class_name": target,
                "source": "ai_ade20k_scene",
                "confidence": round(cconf, 3),
                "area_sq_meters": 0.0,  # pixel space (oblique / non-georeferenced)
                "feature_count": px,
                "geometry_wkt": MultiPolygon([bbox]).wkt,
                "model_name": settings.SCENE_SEG_MODEL,
                "model_version": "ade20k-v1",
                "properties": {
                    "geo_referenced": False,
                    "geometry_space": "pixel",
                    "coverage_pct": pct,
                },
            })

        if annotated_out_path:
            cls._draw_overlay(arr, seg, annotated_out_path)

        avg_conf = float(np.mean(confs)) if confs else 0.0
        inf = round(time.time() - start, 2)
        if progress_callback:
            progress_callback(1, 1)
        # sort features by coverage desc for a tidy review list
        features.sort(key=lambda f: -f["properties"]["coverage_pct"])
        return features, avg_conf, inf, len(features), coverage

    @classmethod
    def _draw_overlay(cls, arr: np.ndarray, seg: np.ndarray, out_path: str):
        H, W = seg.shape
        color = np.zeros((H, W, 3), np.uint8)
        for cid, target in cls._label_to_class.items():
            m = seg == cid
            if m.any():
                color[m] = _CLASS_COLORS.get(target, _DEFAULT_COLOR)
        blend = (0.5 * arr + 0.5 * color).astype(np.uint8)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        PILImage.fromarray(blend).save(out_path, quality=90)
