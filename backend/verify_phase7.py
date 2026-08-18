import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models import ImageryAnalysis, SpatialAnalytics, BenchmarkDefinition, SpatialFeature, OSMFeature
from app.services.analytics_service import AnalyticsService

def verify_phase7():
    db = SessionLocal()
    try:
        # Check if benchmark definitions exist, if not create them for testing
        if db.query(BenchmarkDefinition).count() == 0:
            print("Populating BenchmarkDefinitions...")
            db.add_all([
                BenchmarkDefinition(indicator="tree_cover_pct", unit="%", target_value=15.0, source="Standard A", reference_name="A"),
                BenchmarkDefinition(indicator="road_coverage_pct", unit="%", target_value=5.0, source="Standard B", reference_name="B"),
                BenchmarkDefinition(indicator="hospitals_per_1000", unit="count", target_value=0.5, source="Standard C", reference_name="C"),
                BenchmarkDefinition(indicator="schools_per_1000", unit="count", target_value=1.0, source="Standard D", reference_name="D")
            ])
            db.commit()

        # Fetch a completed analysis
        analysis = db.query(ImageryAnalysis).filter(ImageryAnalysis.status == "completed").first()
        if not analysis:
            print("No completed analysis found to verify.")
            return

        print(f"Verifying Analysis #{analysis.id}")
        
        # We simulate the recalculation of analytics to see if it matches DB
        analytics_dict = AnalyticsService.calculate_analytics(
            db, analysis.id, 
            population_count=analysis.population_count or 12500,
            population_source=analysis.population_source or "Test",
            population_date=analysis.population_date
        )

        db_analytics = db.query(SpatialAnalytics).filter(SpatialAnalytics.analysis_id == analysis.id).first()
        
        if not db_analytics:
            print("No SpatialAnalytics record found. Run a job first.")
            return

        # Verification Checks
        assert round(db_analytics.analysis_area_sq_km, 2) == round(analytics_dict["analysis_area_sq_km"], 2), "Area mismatch"
        assert db_analytics.tree_cover_pct == analytics_dict["tree_cover_pct"], "Tree Cover mismatch"
        assert db_analytics.agriculture_cover_pct == analytics_dict["agriculture_cover_pct"], "Agriculture Cover mismatch"
        assert db_analytics.barren_cover_pct == analytics_dict["barren_cover_pct"], "Barren Cover mismatch"
        assert db_analytics.hospital_count == analytics_dict["hospital_count"], "Hospital count mismatch"
        
        print("Cross-check passed: Independent PostGIS calculation == SpatialAnalytics row")

        # Missing population test
        analytics_no_pop = AnalyticsService.calculate_analytics(
            db, analysis.id, population_count=None
        )
        assert analytics_no_pop["hospitals_per_1000"] is None, "Missing pop should yield None"
        assert analytics_no_pop["infrastructure_score"] is None, "Missing pop should yield None score"
        
        print("Missing Population test passed: Yields None, not 0")
        
        print("PHASE 7 VERIFICATION SUCCESSFUL")

    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    verify_phase7()
