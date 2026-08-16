import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_roles
from app.core.config import settings
from app.models import ImageryAnalysis, Project, SpatialFeature, UrbanBenchmark, User
from app.schemas import AnalysisResponse
from app.services.ai_service import AIService
from app.services.osm_service import OSMService
from app.services.benchmark_service import BenchmarkService

router = APIRouter()

@router.post("/upload", response_model=AnalysisResponse)
def upload_imagery(
    project_id: int = Form(...),
    population_estimate: Optional[int] = Form(1000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"]))
):
    """Upload GeoTIFF / Drone Orthomosaic / Satellite image file for analysis."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {settings.SUPPORTED_EXTENSIONS}"
        )

    upload_dir = os.path.join(settings.DATA_DIR, f"project_{project_id}")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_type = "geotiff" if ext in [".tif", ".tiff", ".geotiff"] else "satellite_png"

    analysis = ImageryAnalysis(
        project_id=project_id,
        filename=file.filename,
        file_path=file_path,
        file_type=file_type,
        crs="EPSG:4326",
        bounds=[77.58, 12.96, 77.60, 12.98], # Default bounding area, updated upon inference
        width=1024,
        height=1024,
        population_estimate=population_estimate or 1000,
        status="pending"
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis

@router.post("/{analysis_id}/run", response_model=AnalysisResponse)
def run_ai_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "planner"]))
):
    """Execute real SegFormer pretrained AI inference + OSM layer enrichment."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found")

    analysis.status = "processing"
    db.commit()

    try:
        bounds = tuple(analysis.bounds or [77.58, 12.96, 77.60, 12.98])
        
        # 1. Run Pretrained SegFormer AI Model
        ai_features, avg_conf, inf_time = AIService.run_inference(analysis.file_path, bounds)

        # 2. Clear old features if re-running
        db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis.id).delete()

        created_features = []
        for feat_dict in ai_features:
            feat = SpatialFeature(
                analysis_id=analysis.id,
                class_name=feat_dict["class_name"],
                source=feat_dict["source"],
                confidence=feat_dict["confidence"],
                area_sq_meters=feat_dict["area_sq_meters"],
                feature_count=feat_dict["feature_count"],
                geometry_json=feat_dict["geometry_json"]
            )
            db.add(feat)
            created_features.append(feat)

        # 3. Query OpenStreetMap Enrichment Layer (Hospitals, Schools, Slums)
        osm_features = OSMService.fetch_osm_enrichment(bounds)
        for feat_dict in osm_features:
            feat = SpatialFeature(
                analysis_id=analysis.id,
                class_name=feat_dict["class_name"],
                source=feat_dict["source"],
                confidence=feat_dict["confidence"],
                area_sq_meters=feat_dict["area_sq_meters"],
                feature_count=feat_dict["feature_count"],
                geometry_json=feat_dict["geometry_json"],
                properties=feat_dict.get("properties")
            )
            db.add(feat)
            created_features.append(feat)

        db.commit()

        # 4. Compute Urban Infrastructure Benchmarks
        bench_dict = BenchmarkService.calculate_benchmarks(
            created_features, bounds, analysis.population_estimate
        )

        db.query(UrbanBenchmark).filter(UrbanBenchmark.analysis_id == analysis.id).delete()
        benchmark = UrbanBenchmark(
            analysis_id=analysis.id,
            population_count=bench_dict["population_count"],
            road_density_km_per_sqkm=bench_dict["road_density_km_per_sqkm"],
            building_coverage_pct=bench_dict["building_coverage_pct"],
            tree_cover_pct=bench_dict["tree_cover_pct"],
            water_cover_pct=bench_dict["water_cover_pct"],
            built_up_ratio=bench_dict["built_up_ratio"],
            hospitals_per_10k_pop=bench_dict["hospitals_per_10k_pop"],
            schools_per_10k_pop=bench_dict["schools_per_10k_pop"],
            infrastructure_score=bench_dict["infrastructure_score"]
        )
        db.add(benchmark)

        analysis.status = "completed"
        analysis.confidence_score = avg_conf
        analysis.inference_time_sec = inf_time
        db.commit()
        db.refresh(analysis)
        return analysis

    except Exception as e:
        analysis.status = "failed"
        analysis.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Inference pipeline error: {e}")

@router.get("/{analysis_id}/status", response_model=AnalysisResponse)
def get_analysis_status(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time analysis status and results."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
