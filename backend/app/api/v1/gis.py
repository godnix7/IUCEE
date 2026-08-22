import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_db, get_current_user, require_spatial_db
from app.models import ImageryAnalysis, SpatialFeature, User

router = APIRouter()

# Map standard colors for UI rendering
CLASS_COLOR_MAP = {
    "road": "#3b82f6",       # Blue
    "building": "#ef4444",   # Red
    "hospital": "#ec4899",   # Pink
    "school": "#eab308",     # Yellow
    "tree_cover": "#22c55e", # Green
    "water": "#06b6d4",      # Cyan
    "slum": "#a855f7",       # Purple
    "open_land": "#f97316"   # Orange
}

@router.get("/analyses/{analysis_id}/geojson")
def get_analysis_geojson(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _spatial: None = Depends(require_spatial_db)
) -> Dict[str, Any]:
    """
    Return unified GeoJSON FeatureCollection of all detected spatial features
    for MapLibre GL rendering. Uses PostGIS ST_AsGeoJSON for geometry serialization.
    """
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Fetch features and serialize geometry to GeoJSON directly in PostGIS
    results = db.query(
        SpatialFeature,
        func.ST_AsGeoJSON(SpatialFeature.geometry).label("geojson")
    ).filter(SpatialFeature.analysis_id == analysis_id).all()

    geojson_features = []
    for f, geojson_str in results:
        props = {
            "id": f.id,
            "class_name": f.class_name,
            "source": f.source,
            "confidence": f.confidence,
            "area_sq_meters": f.area_sq_meters,
            "feature_count": f.feature_count,
            "model_name": f.model_name,
            "model_version": f.model_version,
            "color": CLASS_COLOR_MAP.get(f.class_name, "#94a3b8")
        }
        if f.properties:
            props.update(f.properties)

        # Handle features missing geometry gracefully
        geom = json.loads(geojson_str) if geojson_str else None

        geojson_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props
        })

    return {
        "type": "FeatureCollection",
        "properties": {
            "analysis_id": analysis.id,
            "filename": analysis.filename,
            "crs": analysis.normalized_crs,
            "bounds": analysis.bounds
        },
        "features": geojson_features
    }

from app.models import OSMFeature
from app.services.osm_service import OSMService
import datetime

@router.post("/analyses/{analysis_id}/osm-enrichment")
def run_osm_enrichment(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _spatial: None = Depends(require_spatial_db)
):
    """
    Trigger real OpenStreetMap enrichment specifically scoped to the analysis footprint.
    Filters geometries using PostGIS ST_Intersects against the footprint.
    """
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    if not analysis.bounds:
        raise HTTPException(status_code=400, detail="Analysis has no geographic bounds")

    analysis.osm_enrichment_status = "processing"
    db.commit()

    bounds_tuple = (analysis.bounds[0], analysis.bounds[1], analysis.bounds[2], analysis.bounds[3])
    
    try:
        features, status, error_msg, requested, completed = OSMService.fetch_osm_enrichment(bounds_tuple)
        
        # Prevent duplicates: clean existing OSM features for this analysis
        db.query(OSMFeature).filter(OSMFeature.analysis_id == analysis_id).delete()
        
        for feat in features:
            geom_wkt = feat["geometry"].wkt
            geom_ewkt = f"SRID=4326;{geom_wkt}"
            
            # PostGIS ST_Intersects filtering
            intersects = db.query(func.ST_Intersects(
                func.ST_GeomFromEWKT(geom_ewkt), 
                analysis.footprint
            )).scalar()
            
            if intersects:
                osm_feat = OSMFeature(
                    analysis_id=analysis_id,
                    osm_type=feat["osm_type"],
                    osm_id=feat["osm_id"],
                    category=feat["category"],
                    name=feat["name"],
                    source=feat["source"],
                    tags=feat["tags"],
                    geometry=geom_ewkt
                )
                db.add(osm_feat)

        analysis.osm_enrichment_status = status
        db.commit()
        
        return {
            "status": status,
            "message": "Enrichment complete" if status == "completed" else f"Enrichment partial/failed: {error_msg}",
            "categories_requested": requested,
            "categories_completed": completed
        }

    except Exception as e:
        analysis.osm_enrichment_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analyses/{analysis_id}/osm-status")
def get_osm_status(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    return {
        "status": analysis.osm_enrichment_status,
        "error": None, # Error tracking simplified for now
        "categories_requested": list(OSMService.CATEGORY_MAPPING.values()),
        "started_at": analysis.created_at.isoformat(),
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat() if analysis.osm_enrichment_status in ["completed", "failed", "partial"] else None
    }

@router.get("/analyses/{analysis_id}/osm-enrichment")
def get_osm_geojson(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _spatial: None = Depends(require_spatial_db)
):
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    results = db.query(
        OSMFeature,
        func.ST_AsGeoJSON(OSMFeature.geometry).label("geojson")
    ).filter(OSMFeature.analysis_id == analysis_id).all()

    geojson_features = []
    for f, geojson_str in results:
        props = {
            "source": f.source,
            "osm_id": f.osm_id,
            "osm_type": f.osm_type,
            "category": f.category,
            "name": f.name,
            "tags": f.tags,
            "color": CLASS_COLOR_MAP.get(f.category, "#94a3b8")
        }
        geom = json.loads(geojson_str) if geojson_str else None
        geojson_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props
        })

    return {
        "type": "FeatureCollection",
        "features": geojson_features
    }
