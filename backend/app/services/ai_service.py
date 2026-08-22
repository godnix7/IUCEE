import os
import tempfile
import time
import math
import numpy as np
import torch
import json
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
        cls, image_path: str, transform: Any, metadata: Dict[str, Any], progress_callback=None, job_id: int = None
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
            
            # We use disk-backed memmap to completely avoid RAM exhaustion on massive images!
            CACHE_DIR = "/tmp/iuceee_cache"
            os.makedirs(CACHE_DIR, exist_ok=True)
            
            if job_id:
                logits_fp_name = os.path.join(CACHE_DIR, f"job_{job_id}_logits.dat")
                weights_fp_name = os.path.join(CACHE_DIR, f"job_{job_id}_weights.dat")
                progress_path = os.path.join(CACHE_DIR, f"job_{job_id}_progress.json")
                mode = 'r+' if os.path.exists(logits_fp_name) else 'w+'
            else:
                logits_fp_name = tempfile.NamedTemporaryFile(delete=False).name
                weights_fp_name = tempfile.NamedTemporaryFile(delete=False).name
                progress_path = None
                mode = 'w+'

            completed_tiles = set()
            if progress_path and os.path.exists(progress_path) and mode == 'r+':
                try:
                    with open(progress_path, 'r') as f:
                        completed_tiles = set(tuple(x) for x in json.load(f))
                except Exception as e:
                    print(f"[AIService] Failed to load progress: {e}")
                    completed_tiles = set()
                    mode = 'w+' # reset if corrupted

            global_logits = np.memmap(logits_fp_name, dtype=np.float16, mode=mode, shape=(num_classes, height, width))
            global_weights = np.memmap(weights_fp_name, dtype=np.float16, mode=mode, shape=(height, width))
            
            # Read all RGB bands (Assuming 1,2,3 are R,G,B)
            img_np = src.read([1, 2, 3]) 
            img_np = np.transpose(img_np, (1, 2, 0)) # -> (H, W, 3)

        # Calculate grid
        x_steps = math.ceil((width - cls.TILE_SIZE) / cls.STRIDE) + 1 if width > cls.TILE_SIZE else 1
        y_steps = math.ceil((height - cls.TILE_SIZE) / cls.STRIDE) + 1 if height > cls.TILE_SIZE else 1
        total_tiles = x_steps * y_steps

        tiles_processed = len(completed_tiles) if completed_tiles else 0
        if progress_callback and tiles_processed > 0:
            progress_callback(tiles_processed, total_tiles)
        
        try:
            with torch.inference_mode():
                for y_idx in range(y_steps):
                    for x_idx in range(x_steps):
                        if (x_idx, y_idx) in completed_tiles:
                            continue
                            
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
                        logits_np = upsampled_logits.squeeze(0).cpu().numpy().astype(np.float16)
                        
                        # Get blend weight
                        weight = cls._get_weight_window(tile_h, tile_w).astype(np.float16)
                        
                        # Accumulate
                        global_logits[:, start_y:end_y, start_x:end_x] += (logits_np * weight)
                        global_weights[start_y:end_y, start_x:end_x] += weight
                        
                        # Explicitly delete intermediate heavy objects to prevent RAM fragmentation
                        del tile_img, inputs, outputs, logits, upsampled_logits, logits_np, weight
                        
                        if progress_path:
                            completed_tiles.add((x_idx, y_idx))
                            # update progress file
                            with open(progress_path, 'w') as f:
                                json.dump(list(completed_tiles), f)
                            # flush memmap periodically to ensure persistence (every 5 tiles)
                            if len(completed_tiles) % 5 == 0:
                                global_logits.flush()
                                global_weights.flush()
                                
                        tiles_processed += 1
                        if progress_callback:
                            progress_callback(tiles_processed, total_tiles)

            # --- POST-PROCESSING IN CHUNKS ---
            seg_mask = np.zeros((height, width), dtype=np.uint8)
            conf_map = np.zeros((height, width), dtype=np.float16)
            
            CHUNK_ROWS = 1024
            for r in range(0, height, CHUNK_ROWS):
                r_end = min(height, r + CHUNK_ROWS)
                
                # Load chunk into RAM
                w_chunk = np.array(global_weights[r:r_end, :])
                w_chunk[w_chunk == 0] = 1.0 # prevent division by zero
                
                l_chunk = np.array(global_logits[:, r:r_end, :])
                l_chunk /= w_chunk
                
                # Softmax for probabilities and argmax for masks on chunk
                tensor_chunk = torch.from_numpy(l_chunk.astype(np.float32)).unsqueeze(0)
                probs = torch.softmax(tensor_chunk, dim=1)
                c_map, s_mask = torch.max(probs, dim=1)
                
                seg_mask[r:r_end, :] = s_mask.squeeze(0).numpy().astype(np.uint8)
                conf_map[r:r_end, :] = c_map.squeeze(0).numpy().astype(np.float16)
                
                del w_chunk, l_chunk, tensor_chunk, probs, c_map, s_mask
        finally:
            # Clean up memmaps
            del global_logits, global_weights
            if not job_id:
                try:
                    os.remove(logits_fp_name)
                    os.remove(weights_fp_name)
                except Exception:
                    pass

        features = []
        confidences = []

        src_crs = metadata.get("crs")
        # A GeoTIFF is only truly georeferenced if it carries a CRS AND a non-identity
        # affine transform. Plain JP/PNG drone stills have neither -> their pixel
        # coordinates must NOT be reprojected as if they were lon/lat (that yields NaN
        # areas and off-world geometry).
        try:
            identity_transform = transform is None or transform.is_identity
        except Exception:
            identity_transform = transform is None
        georef = src_crs is not None and not identity_transform
        src_crs_str = None
        if georef:
            src_crs_str = f"EPSG:{src_crs.to_epsg()}" if src_crs.is_epsg_code else src_crs.to_wkt()

        import cv2
        # Step 7: Class Consolidation
        for model_id, target_class in cls.LOVEDA_TO_URBANSENSE.items():
            class_mask = (seg_mask == model_id).astype(np.uint8)
            if np.sum(class_mask) == 0:
                continue

            # SMOOTH OUT NOISE TO PREVENT MILLIONS OF POLYGONS (OOM FIX)
            # A 5x5 kernel morphological opening removes tiny salt-and-pepper artifacts.
            kernel = np.ones((5,5), np.uint8)
            class_mask = cv2.morphologyEx(class_mask, cv2.MORPH_OPEN, kernel)
            
            if np.sum(class_mask) == 0:
                continue

            # Confidence for this class
            class_conf = float(np.mean(conf_map[class_mask == 1]))
            confidences.append(class_conf)
            # Step 10: Polygonization via OpenCV (Ultra-low memory)
            from shapely.geometry import Polygon
            from shapely.affinity import affine_transform
            from app.services.geo_service import GeoService
            
            contours, _ = cv2.findContours(class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            CHUNK_SIZE = 5000
            current_chunk = []
            
            def flush_chunk():
                if not current_chunk:
                    return
                    
                multi_poly_src_chunk = MultiPolygon(current_chunk)
                
                if georef:
                    # Reproject to Geographic (EPSG:4326) then measure area in a metric CRS
                    out_geom = GeoService.transform_geometry(multi_poly_src_chunk, src_crs_str, "EPSG:4326")
                    metric_crs = GeoService.choose_metric_crs(out_geom)
                    multi_poly_metric = GeoService.transform_geometry(out_geom, "EPSG:4326", metric_crs)
                    a = multi_poly_metric.area
                    chunk_area = round(a, 2) if math.isfinite(a) else 0.0
                else:
                    out_geom = multi_poly_src_chunk
                    chunk_area = 0.0

                features.append({
                    "class_name": target_class,
                    "source": "ai_segformer_loveda",
                    "confidence": round(class_conf, 3),
                    "area_sq_meters": chunk_area,
                    "feature_count": len(current_chunk),
                    "geometry_wkt": out_geom.wkt,
                    "model_name": settings.PRETRAINED_SEGFORMER_MODEL,
                    "model_version": "v1.0",
                    "properties": {
                        "geo_referenced": georef,
                        "geometry_space": "geographic" if georef else "pixel",
                    }
                })
                current_chunk.clear()
            
            for contour in contours:
                if len(contour) < 3:
                    continue
                
                # Extremely fast C-level filter to skip noise before heavy Shapely instantiation
                if cv2.contourArea(contour) < 4.0:
                    continue
                    
                # Create Shapely polygon
                poly = Polygon(contour.squeeze(1))
                if not poly.is_valid:
                    poly = make_valid(poly)
                
                if poly.is_empty or poly.area < 1e-6:
                    continue
                    
                # Apply Affine Transform if we are georeferenced
                if not identity_transform:
                    # rasterio.Affine(a,b,c,d,e,f) -> shapely matrix: [a, b, d, e, xoff, yoff] = [a, b, d, e, c, f]
                    a, b, c, d, e, f = transform.a, transform.b, transform.c, transform.d, transform.e, transform.f
                    poly = affine_transform(poly, [a, b, d, e, c, f])
                
                if poly.geom_type == 'MultiPolygon':
                    for p in poly.geoms:
                        if p.area >= 1e-6:
                            current_chunk.append(p)
                elif poly.geom_type == 'Polygon':
                    current_chunk.append(poly)
                    
                if len(current_chunk) >= CHUNK_SIZE:
                    flush_chunk()
                    
            # Flush remaining polygons
            flush_chunk()

        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        inf_time = round(time.time() - start_time, 2)
        return features, avg_conf, inf_time, tiles_processed

    @classmethod
    def cleanup_job_cache(cls, job_id: int):
        """Clean up the persistent memmap cache files for a specific job."""
        if not job_id:
            return
        CACHE_DIR = "/tmp/iuceee_cache"
        for ext in ["_logits.dat", "_weights.dat", "_progress.json"]:
            path = os.path.join(CACHE_DIR, f"job_{job_id}{ext}")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"[AIService] Failed to remove cache file {path}: {e}")
