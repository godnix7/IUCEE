from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models import ImageryAnalysis, SpatialAnalytics, User
from app.schemas import DashboardStatsResponse, AnalysisResponse, AnalyticsResponse

router = APIRouter()

@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregate enterprise dashboard stats.
    """
    total_analyses = db.query(ImageryAnalysis).count()
    recent_analyses_orm = db.query(ImageryAnalysis).order_by(ImageryAnalysis.id.desc()).limit(5).all()
    recent_analyses = [AnalysisResponse.from_orm(a) for a in recent_analyses_orm]
    active_users = db.query(User).filter(User.is_active == True).count()
    queue_count = db.query(ImageryAnalysis).filter(ImageryAnalysis.status == "pending").count()

    return {
        "total_analyses": total_analyses,
        "recent_analyses": recent_analyses,
        "processing_queue_count": queue_count,
        "active_users_count": active_users
    }

@router.get("/analyses/{analysis_id}", response_model=AnalyticsResponse)
def get_analysis_analytics(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    if analysis.status != "completed":
        return {"analysis_id": analysis_id, "status": analysis.status}
        
    analytics = db.query(SpatialAnalytics).filter(SpatialAnalytics.analysis_id == analysis_id).first()
    if not analytics:
        return {"analysis_id": analysis_id, "status": "no_data"}
        
    return {
        "analysis_id": analysis_id,
        "area_sq_km": analytics.analysis_area_sq_km,
        "status": analysis.status,
        "population": {
            "count": analytics.population_count,
            "source": analytics.population_source,
            "date": analytics.population_date.isoformat() if analytics.population_date else None
        },
        "infrastructure": {
            "road_area_sq_m": analytics.road_area_sq_m,
            "road_coverage_pct": analytics.road_coverage_pct,
            "building_coverage_pct": analytics.building_coverage_pct,
            "tree_cover_pct": analytics.tree_cover_pct,
            "water_cover_pct": analytics.water_cover_pct,
            "agriculture_cover_pct": analytics.agriculture_cover_pct,
            "barren_cover_pct": analytics.barren_cover_pct
        },
        "facilities": {
            "hospitals": analytics.hospital_count,
            "schools": analytics.school_count,
            "police": analytics.police_count,
            "fire_stations": analytics.fire_station_count
        },
        "normalized": {
            "hospitals_per_1000": analytics.hospitals_per_1000,
            "schools_per_1000": analytics.schools_per_1000
        },
        "score": analytics.infrastructure_score,
        "component_scores": analytics.component_scores,
        "formula_version": analytics.formula_version,
        "calculated_at": analytics.calculated_at.isoformat() if analytics.calculated_at else None
    }
