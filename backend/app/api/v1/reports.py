import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models import ImageryAnalysis, SpatialAnalytics, SpatialFeature, User
from app.services.pdf_service import PDFService

router = APIRouter()

@router.get("/analyses/{analysis_id}/pdf")
def get_pdf_report(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate and download Executive PDF Report for an analysis."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analytics = db.query(SpatialAnalytics).filter(SpatialAnalytics.analysis_id == analysis_id).first()
    features = db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis_id).all()
    from app.models import BenchmarkDefinition
    benchmarks = db.query(BenchmarkDefinition).all()

    pdf_bytes = PDFService.generate_analysis_pdf(analysis, analytics, features, benchmarks)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=UrbanSense_Report_Analysis_{analysis_id}.pdf"
        }
    )

@router.get("/analyses/{analysis_id}/csv")
def get_csv_export(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download CSV summary of detected spatial infrastructure features."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    features = db.query(SpatialFeature).filter(SpatialFeature.analysis_id == analysis_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Feature ID", "Category", "Source Engine", "Confidence", "Area (sq meters)", "Feature Count"])

    for f in features:
        writer.writerow([
            f.id,
            f.class_name,
            f.source,
            f.confidence,
            f.area_sq_meters,
            f.feature_count
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=UrbanSense_Features_Analysis_{analysis_id}.csv"
        }
    )

@router.get("/analyses/{analysis_id}/geojson")
def get_geojson_export(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download GeoJSON summary of detected spatial infrastructure features."""
    analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    from sqlalchemy import func
    import json
    
    features = db.query(
        SpatialFeature,
        func.ST_AsGeoJSON(SpatialFeature.geometry).label('geometry_json')
    ).filter(SpatialFeature.analysis_id == analysis_id).all()
    
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    for row in features:
        f = row.SpatialFeature
        geom_json = json.loads(row.geometry_json) if row.geometry_json else None
        feature = {
            "type": "Feature",
            "geometry": geom_json,
            "properties": {
                "id": f.id,
                "class_name": f.class_name,
                "source": f.source,
                "confidence": f.confidence,
                "area_sq_meters": f.area_sq_meters,
                "feature_count": f.feature_count,
            }
        }
        geojson["features"].append(feature)
        
    import json
    return Response(
        content=json.dumps(geojson),
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f"attachment; filename=UrbanSense_Features_Analysis_{analysis_id}.geojson"
        }
    )
