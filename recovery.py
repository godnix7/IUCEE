import os
import sys
import numpy as np
import cv2
import math
import rasterio
from rasterio.windows import Window
from rasterio.features import shapes
from shapely.geometry import Polygon, MultiPolygon
from shapely.affinity import affine_transform
from shapely.validation import make_valid
from app.core.database import SessionLocal
from app.models import ProcessingJob, ImageryAnalysis, SpatialFeature
from app.services.storage_service import StorageService
from app.services.ai_service import AIService
import tempfile

def run():
    db = SessionLocal()
    analysis_id = 26
    job_id = 32
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    
    print("Downloading file...")
    _, ext = os.path.splitext(analysis.file_path)
    fd, temp_file_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    StorageService.download_file(analysis.file_path, temp_file_path)
    
    with rasterio.open(temp_file_path) as src:
        meta = src.meta
        transform = src.transform
        width = src.width
        height = src.height
        
    print(f"Size: {width}x{height}")
    
    # We found the files tmpkii7u_cn (logits, 15GB) and tmpuix44due (weights, 1.8GB)
    global_logits = np.memmap('/tmp/tmpkii7u_cn', dtype=np.float16, mode='r', shape=(7, height, width))
    global_weights = np.memmap('/tmp/tmpuix44due', dtype=np.float16, mode='r', shape=(height, width))
    
    print("Starting post processing...")
    
    seg_mask = np.zeros((height, width), dtype=np.uint8)
    conf_map = np.zeros((height, width), dtype=np.float16)
    
    import torch
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
        
    features = []
    
    try:
        identity_transform = transform is None or transform.is_identity
    except Exception:
        identity_transform = transform is None
        
    src_crs = meta.get("crs")
    georef = src_crs is not None and not identity_transform
    src_crs_str = f"EPSG:{src_crs.to_epsg()}" if georef and src_crs.is_epsg_code else (src_crs.to_wkt() if georef else None)
    
    print("Polygonizing...")
    for model_id, target_class in AIService.LOVEDA_TO_URBANSENSE.items():
        class_mask = (seg_mask == model_id).astype(np.uint8)
        if np.sum(class_mask) == 0:
            continue
            
        kernel = np.ones((5,5), np.uint8)
        class_mask = cv2.morphologyEx(class_mask, cv2.MORPH_OPEN, kernel)
        
        if np.sum(class_mask) == 0:
            continue
            
        class_conf = float(np.mean(conf_map[class_mask == 1]))
        
        contours, _ = cv2.findContours(class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for contour in contours:
            if len(contour) < 3:
                continue
            poly = Polygon(contour.squeeze(1))
            if not poly.is_valid:
                poly = make_valid(poly)
            if poly.is_empty or poly.area < 1e-6:
                continue
                
            if not identity_transform:
                a, b, c, d, e, f = transform.a, transform.b, transform.c, transform.d, transform.e, transform.f
                poly = affine_transform(poly, [a, b, d, e, c, f])
                
            if poly.geom_type == 'MultiPolygon':
                for p in poly.geoms:
                    if p.area >= 1e-6:
                        polygons.append(p)
            elif poly.geom_type == 'Polygon':
                polygons.append(poly)
                
        if not polygons:
            continue
            
        multi_poly_src = MultiPolygon(polygons)
        
        from app.services.geo_service import GeoService
        from app.core.config import settings
        
        if georef:
            out_geom = GeoService.transform_geometry(multi_poly_src, src_crs_str, "EPSG:4326")
            metric_crs = GeoService.choose_metric_crs(out_geom)
            multi_poly_metric = GeoService.transform_geometry(out_geom, "EPSG:4326", metric_crs)
            a = multi_poly_metric.area
            area_sq_meters = round(a, 2) if math.isfinite(a) else 0.0
        else:
            out_geom = multi_poly_src
            area_sq_meters = 0.0
            
        # IMPORTANT FIX: CHUNK MULTIPOLYGONS SO WE DON'T SAVE 1GB STRINGS
        CHUNK_SIZE = 5000
        
        polygons_list = list(out_geom.geoms) if out_geom.geom_type == 'MultiPolygon' else [out_geom]
        for i in range(0, len(polygons_list), CHUNK_SIZE):
            chunk = polygons_list[i:i + CHUNK_SIZE]
            chunk_multi = MultiPolygon(chunk)
            
            features.append({
                "class_name": target_class,
                "source": "ai_segformer_loveda",
                "confidence": round(class_conf, 3),
                "area_sq_meters": area_sq_meters * (len(chunk) / len(polygons_list)),
                "feature_count": len(chunk),
                "geometry_wkt": chunk_multi.wkt,
                "model_name": settings.PRETRAINED_SEGFORMER_MODEL,
                "model_version": "v1.0",
                "properties": {
                    "geo_referenced": georef,
                    "geometry_space": "geographic" if georef else "pixel",
                }
            })
            
    print(f"Generated {len(features)} feature chunks")
    
    # Clean existing features for idempotency
    db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis.id).delete()
    
    for feat_dict in features:
        feat = SpatialFeature(
            analysis_id=analysis.id,
            class_name=feat_dict["class_name"],
            source=feat_dict["source"],
            confidence=feat_dict["confidence"],
            area_sq_meters=feat_dict["area_sq_meters"],
            feature_count=feat_dict["feature_count"],
            geometry=f"SRID=4326;{feat_dict['geometry_wkt']}",
            model_name=feat_dict.get("model_name"),
            model_version=feat_dict.get("model_version"),
            properties=feat_dict.get("properties"),
        )
        db.add(feat)
    db.commit()
    
    job.progress = 100
    job.status = "completed"
    job.current_stage = "completed"
    db.commit()
    print("DONE!")

if __name__ == "__main__":
    run()
