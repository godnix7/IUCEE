import os
import time
import math
import numpy as np
import torch
import rasterio
from rasterio.windows import Window
from rasterio.features import shapes
from shapely.geometry import shape, MultiPolygon
from shapely.validation import make_valid
from typing import Dict, List, Any, Tuple
from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
from app.core.config import settings

class AIService:
    _processor = None
    _model = None
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # LoveDA classes:
    # 0: Ignore, 1: Background, 2: Building, 3: Road
    # 4: Water, 5: Barren, 6: Forest, 7: Agricultural
    LOVEDA_TO_URBANSENSE = {
        2: "building",
        3: "road",
        4: "water",
        5: "barren_land",
        6: "tree_cover",
        7: "agriculture"
    }
    
    TILE_SIZE = 512
    STRIDE = 384  # ~25% overlap (512 - 128)

    @classmethod
    def load_model(cls):
        """Lazy load pretrained SegFormer LoveDA model and AutoImageProcessor."""
        if cls._model is None:
            model_name = settings.PRETRAINED_SEGFORMER_MODEL
            try:
                print(f"[AIService] Loading LoveDA model: {model_name} on {cls._device}")
                cls._processor = SegformerImageProcessor.from_pretrained(model_name)
                cls._model = SegformerForSemanticSegmentation.from_pretrained(model_name)
                cls._model.to(cls._device)
                cls._model.eval()
                print("[AIService] Model loaded successfully.")
            except Exception as e:
                print(f"[AIService] Critical Error loading model '{model_name}': {e}")
                raise RuntimeError(f"Failed to load AI model '{model_name}': {e}")

    @classmethod
    def _get_weight_window(cls, height: int, width: int) -> np.ndarray:
        """Create a 2D Hann window for smooth overlap blending."""
        w_y = np.hanning(height)
        w_x = np.hanning(width)
        weight_2d = np.outer(w_y, w_x)
        return weight_2d.astype(np.float32)

    @classmethod
    def run_inference(
        cls, image_path: str, transform: Any, metadata: Dict[str, Any], progress_callback=None
    ) -> Tuple[List[dict], float, float, int]:
        """
        Run pretrained SegFormer B2 LoveDA inference over a large GeoTIFF.
        Returns: (features_list, avg_confidence, inference_time_sec, tiles_processed)
        """
        start_time = time.time()
        cls.load_model()

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        # Read Raster and validate
        with rasterio.open(image_path) as src:
            if src.count < 3:
                raise ValueError(f"Raster requires at least 3 bands (RGB). Found {src.count}.")
            
            width = src.width
            height = src.height
            
            # Estimate global arrays
            num_classes = len(cls._model.config.id2label)
            
            # Using overlapping window sliding over the whole image.
            # To avoid RAM explosion on massive rasters, we do tile-based processing.
            # However, for global logits, we need a canvas.
            global_logits = np.zeros((num_classes, height, width), dtype=np.float32)
            global_weights = np.zeros((height, width), dtype=np.float32)
            
            # Read all RGB bands (Assuming 1,2,3 are R,G,B)
            img_np = src.read([1, 2, 3]) 
            img_np = np.transpose(img_np, (1, 2, 0)) # -> (H, W, 3)

        tiles_processed = 0
        
        # Calculate grid
        x_steps = math.ceil((width - cls.TILE_SIZE) / cls.STRIDE) + 1 if width > cls.TILE_SIZE else 1
        y_steps = math.ceil((height - cls.TILE_SIZE) / cls.STRIDE) + 1 if height > cls.TILE_SIZE else 1
        total_tiles = x_steps * y_steps

        with torch.inference_mode():
            for y_idx in range(y_steps):
                for x_idx in range(x_steps):
                    # Calculate tile bounds
                    start_y = y_idx * cls.STRIDE
                    start_x = x_idx * cls.STRIDE
                    
                    # Adjust if we overshoot the image boundaries
                    if start_y + cls.TILE_SIZE > height:
                        start_y = max(0, height - cls.TILE_SIZE)
                    if start_x + cls.TILE_SIZE > width:
                        start_x = max(0, width - cls.TILE_SIZE)
                        
                    end_y = min(height, start_y + cls.TILE_SIZE)
                    end_x = min(width, start_x + cls.TILE_SIZE)
                    
                    tile_h = end_y - start_y
                    tile_w = end_x - start_x
                    
                    # Extract tile
                    tile_img = img_np[start_y:end_y, start_x:end_x, :]
                    
                    # Prepare for HuggingFace (expects list of images or numpy array)
                    inputs = cls._processor(images=tile_img, return_tensors="pt").to(cls._device)
                    outputs = cls._model(**inputs)
                    
                    logits = outputs.logits # (1, num_classes, H/4, W/4)
                    
                    # Interpolate logits to match the EXACT tile size extracted (e.g. 512x512 or edge size)
                    upsampled_logits = torch.nn.functional.interpolate(
                        logits,
                        size=(tile_h, tile_w),
                        mode="bilinear",
                        align_corners=False
                    )
                    
                    # Squeeze batch dimension
                    logits_np = upsampled_logits.squeeze(0).cpu().numpy()
                    
                    # Get blend weight
                    weight = cls._get_weight_window(tile_h, tile_w)
                    
                    # Accumulate
                    global_logits[:, start_y:end_y, start_x:end_x] += (logits_np * weight)
                    global_weights[start_y:end_y, start_x:end_x] += weight
                    
                    tiles_processed += 1
                    if progress_callback:
                        progress_callback(tiles_processed, total_tiles)

        # Normalize logits by weights
        global_weights[global_weights == 0] = 1.0 # prevent division by zero
        global_logits /= global_weights
        
        # Softmax for probabilities and argmax for masks
        global_tensor = torch.from_numpy(global_logits).unsqueeze(0)
        probabilities = torch.softmax(global_tensor, dim=1)
        conf_map, seg_mask = torch.max(probabilities, dim=1)
        
        seg_mask = seg_mask.squeeze(0).numpy().astype(np.uint8)
        conf_map = conf_map.squeeze(0).numpy()

        features = []
        confidences = []

        src_crs = metadata.get("crs")
        src_crs_str = "EPSG:4326"
        if src_crs:
            src_crs_str = f"EPSG:{src_crs.to_epsg()}" if src_crs.is_epsg_code else src_crs.to_wkt()

        # Step 7: Class Consolidation
        for model_id, target_class in cls.LOVEDA_TO_URBANSENSE.items():
            class_mask = (seg_mask == model_id).astype(np.uint8)
            if np.sum(class_mask) == 0:
                continue

            # Confidence for this class
            class_conf = float(np.mean(conf_map[class_mask == 1]))
            confidences.append(class_conf)
            
            # Step 10: Polygonization via Rasterio
            shapes_gen = shapes(class_mask, mask=class_mask, transform=transform)
            
            polygons = []
            
            for geom_dict, val in shapes_gen:
                if val != 1:
                    continue
                    
                # Convert to Shapely geometry
                poly = shape(geom_dict)
                if not poly.is_valid:
                    poly = make_valid(poly)
                
                # Cleanup: remove zero-area or tiny slivers
                if poly.is_empty or poly.area < 1e-6:
                    continue
                    
                if poly.geom_type == 'MultiPolygon':
                    for p in poly.geoms:
                        if p.area >= 1e-6:
                            polygons.append(p)
                elif poly.geom_type == 'Polygon':
                    polygons.append(poly)
            
            if not polygons:
                continue
                
            # Combine into a single MultiPolygon in Source CRS
            multi_poly_src = MultiPolygon(polygons)
            
            # Reproject to Geographic (EPSG:4326)
            from app.services.geo_service import GeoService
            multi_poly_4326 = GeoService.transform_geometry(multi_poly_src, src_crs_str, "EPSG:4326")
            
            # Calculate Area using Dynamic Metric CRS
            metric_crs = GeoService.choose_metric_crs(multi_poly_4326)
            multi_poly_metric = GeoService.transform_geometry(multi_poly_4326, "EPSG:4326", metric_crs)
            area_sq_meters = multi_poly_metric.area

            features.append({
                "class_name": target_class,
                "source": "ai_segformer_loveda",
                "confidence": round(class_conf, 3),
                "area_sq_meters": round(area_sq_meters, 2),
                "feature_count": len(polygons),
                "geometry_wkt": multi_poly_4326.wkt,
                "model_name": settings.PRETRAINED_SEGFORMER_MODEL,
                "model_version": "v1.0"
            })

        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        inf_time = round(time.time() - start_time, 2)
        return features, avg_conf, inf_time, tiles_processed
