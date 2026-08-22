import os
import time
import math
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
import rasterio
import torch
from PIL import Image as PILImage, ImageDraw, ImageFont
from shapely.geometry import box as shapely_box, MultiPolygon
from transformers import AutoImageProcessor, AutoModelForObjectDetection

from app.core.config import settings


# Stable RGB colors per class for the annotated overlay
_CLASS_COLORS = {
    "person": (239, 68, 68),
    "bicycle": (168, 85, 247),
    "car": (59, 130, 246),
    "motorcycle": (236, 72, 153),
    "bus": (234, 179, 8),
    "truck": (249, 115, 22),
    "train": (14, 165, 233),
    "boat": (6, 182, 212),
}
_DEFAULT_COLOR = (148, 163, 184)


class DetectionService:
    """
    Object detection for oblique / drone imagery (e.g. VisDrone) using a COCO-pretrained
    transformers model. This is the counterpart to AIService (semantic segmentation) and is
    selected when analysis_mode == 'detection'.

    Detections are aggregated per class into a single SpatialFeature (a MultiPolygon of the
    bounding boxes) so they flow through the existing GeoJSON / analytics plumbing, while a
    human-readable annotated overlay image is produced for display.
    """

    _processor = None
    _model = None
    _device = "cuda" if torch.cuda.is_available() else "cpu"

    @classmethod
    def load_model(cls):
        if cls._model is None:
            name = settings.DETECTION_MODEL
            try:
                print(f"[DetectionService] Loading detection model: {name} on {cls._device}")
                cls._processor = AutoImageProcessor.from_pretrained(name)
                cls._model = AutoModelForObjectDetection.from_pretrained(name)
                cls._model.to(cls._device)
                cls._model.eval()
                print("[DetectionService] Model loaded successfully.")
            except Exception as e:
                raise RuntimeError(f"Failed to load detection model '{name}': {e}")

    @classmethod
    def _is_georeferenced(cls, transform, crs) -> bool:
        """True only if the raster carries a real CRS and a non-identity affine transform."""
        if crs is None:
            return False
        try:
            if transform is None or transform.is_identity:
                return False
        except Exception:
            return False
        return True

    @classmethod
    def run_detection(
        cls,
        image_path: str,
        transform: Any,
        metadata: Dict[str, Any],
        annotated_out_path: Optional[str] = None,
        progress_callback=None,
    ) -> Tuple[List[dict], float, float, int, Dict[str, int]]:
        """
        Returns: (features_list, avg_confidence, inference_time_sec, num_detections, class_counts)
        Each feature dict matches the shape consumed by the persistence layer in tasks.py.
        """
        start_time = time.time()
        cls.load_model()

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        crs = metadata.get("crs")
        georef = cls._is_georeferenced(transform, crs)

        with rasterio.open(image_path) as src:
            if src.count < 3:
                raise ValueError(f"Detection requires at least 3 bands (RGB). Found {src.count}.")
            arr = np.transpose(src.read([1, 2, 3]), (1, 2, 0))  # H,W,3
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        H, W = arr.shape[:2]
        pil = PILImage.fromarray(arr)

        if progress_callback:
            progress_callback(0, 1)

        with torch.inference_mode():
            inputs = cls._processor(images=pil, return_tensors="pt").to(cls._device)
            outputs = cls._model(**inputs)
        results = cls._processor.post_process_object_detection(
            outputs, threshold=settings.DETECTION_THRESHOLD, target_sizes=[(H, W)]
        )[0]

        id2label = cls._model.config.id2label
        allowed = set(settings.DETECTION_CLASSES)

        # Group detections by class
        by_class: Dict[str, List[Dict[str, Any]]] = {}
        for score, label, bbox in zip(results["scores"], results["labels"], results["boxes"]):
            name = id2label[int(label)]
            if name not in allowed:
                continue
            x0, y0, x1, y1 = [float(v) for v in bbox.tolist()]
            x0, x1 = max(0.0, min(x0, x1)), min(float(W), max(x0, x1))
            y0, y1 = max(0.0, min(y0, y1)), min(float(H), max(y0, y1))
            if x1 - x0 < 1 or y1 - y0 < 1:
                continue
            by_class.setdefault(name, []).append(
                {"bbox": [x0, y0, x1, y1], "score": round(float(score), 3)}
            )

        # Lazy import to avoid cycles
        from app.services.geo_service import GeoService

        src_crs_str = None
        if georef and crs is not None:
            src_crs_str = f"EPSG:{crs.to_epsg()}" if crs.is_epsg_code else crs.to_wkt()

        features: List[dict] = []
        class_counts: Dict[str, int] = {}
        all_scores: List[float] = []

        for name, dets in by_class.items():
            class_counts[name] = len(dets)
            polys_geo = []       # geometry stored in DB (world coords if georef, else pixel)
            area_sq_m = 0.0
            for d in dets:
                x0, y0, x1, y1 = d["bbox"]
                all_scores.append(d["score"])
                if georef:
                    # pixel corners -> source-CRS world coords via affine transform
                    wx0, wy0 = transform * (x0, y0)
                    wx1, wy1 = transform * (x1, y1)
                    world_box = shapely_box(min(wx0, wx1), min(wy0, wy1), max(wx0, wx1), max(wy0, wy1))
                    box_4326 = GeoService.transform_geometry(world_box, src_crs_str, "EPSG:4326")
                    polys_geo.append(box_4326)
                    d["bbox_geo"] = list(box_4326.bounds)
                else:
                    polys_geo.append(shapely_box(x0, y0, x1, y1))

            if georef and polys_geo:
                try:
                    mp = MultiPolygon(polys_geo)
                    metric_crs = GeoService.choose_metric_crs(mp)
                    mp_m = GeoService.transform_geometry(mp, "EPSG:4326", metric_crs)
                    a = mp_m.area
                    area_sq_m = round(a, 2) if math.isfinite(a) else 0.0
                except Exception:
                    area_sq_m = 0.0

            multi = MultiPolygon(polys_geo)
            mean_conf = round(float(np.mean([d["score"] for d in dets])), 3)
            features.append({
                "class_name": name,
                "source": "detection_yolos",
                "confidence": mean_conf,
                "area_sq_meters": area_sq_m,
                "feature_count": len(dets),
                "geometry_wkt": multi.wkt,
                "model_name": settings.DETECTION_MODEL,
                "model_version": "coco-v1",
                "properties": {
                    "geo_referenced": georef,
                    "geometry_space": "geographic" if georef else "pixel",
                    "detections": dets,
                },
            })

        # ---- Annotated overlay image ----
        if annotated_out_path:
            cls._draw_overlay(arr.copy(), by_class, annotated_out_path)

        num_detections = int(sum(class_counts.values()))
        avg_conf = float(np.mean(all_scores)) if all_scores else 0.0
        inf_time = round(time.time() - start_time, 2)
        if progress_callback:
            progress_callback(1, 1)
        return features, avg_conf, inf_time, num_detections, class_counts

    @classmethod
    def _draw_overlay(cls, arr: np.ndarray, by_class: Dict[str, List[Dict[str, Any]]], out_path: str):
        img = PILImage.fromarray(arr).convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        for name, dets in by_class.items():
            color = _CLASS_COLORS.get(name, _DEFAULT_COLOR)
            for d in dets:
                x0, y0, x1, y1 = d["bbox"]
                draw.rectangle([x0, y0, x1, y1], outline=color, width=3)
                label = f"{name} {d['score']:.2f}"
                ty = max(0, y0 - 12)
                try:
                    tb = draw.textbbox((x0, ty), label, font=font)
                    draw.rectangle(tb, fill=color)
                except Exception:
                    pass
                draw.text((x0, ty), label, fill=(255, 255, 255), font=font)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, quality=90)
