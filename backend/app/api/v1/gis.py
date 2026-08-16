from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
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
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Return unified GeoJSON FeatureCollection of all detected spatial features
    for MapLibre GL rendering.
    """
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    features = db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis_id).all()

    geojson_features = []
    for f in features:
        props = {
            "id": f.id,
            "class_name": f.class_name,
            "source": f.source,
            "confidence": f.confidence,
            "area_sq_meters": f.area_sq_meters,
            "feature_count": f.feature_count,
            "color": CLASS_COLOR_MAP.get(f.class_name, "#94a3b8")
        }
        if f.properties:
            props.update(f.properties)

        geojson_features.append({
            "type": "Feature",
            "geometry": f.geometry_json,
            "properties": props
        })

    return {
        "type": "FeatureCollection",
        "properties": {
            "analysis_id": analysis.id,
            "filename": analysis.filename,
            "crs": analysis.crs,
            "bounds": analysis.bounds
        },
        "features": geojson_features
    }
