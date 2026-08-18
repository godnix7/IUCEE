from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import json

class AnalyticsService:
    @classmethod
    def calculate_analytics(
        cls,
        db: Session,
        analysis_id: int,
        population_count: int | None = None,
        population_source: str | None = None,
        population_date: datetime | None = None
    ) -> Dict[str, Any]:
        """
        Calculate precise geospatial analytics via PostGIS directly from the verified database schema.
        """
        # 1. Total Analysis Area in sq km (using metric geography ST_Area)
        area_query = text("""
            SELECT ST_Area(footprint::geography) 
            FROM imagery_analyses 
            WHERE id = :analysis_id
        """)
        total_area_sq_m = db.execute(area_query, {"analysis_id": analysis_id}).scalar()
        if not total_area_sq_m or total_area_sq_m <= 0:
            return {"status": "no_data"}
            
        total_area_sq_km = total_area_sq_m / 1000000.0

        # 2. Aggregated Class Areas (preventing double count via ST_Union)
        # Using ST_Union ensures overlapping polygons from model tiling don't inflate area.
        class_areas = {}
        for cls_name in ["road", "building", "tree_cover", "water", "barren_land", "agriculture"]:
            cls_query = text("""
                SELECT ST_Area(ST_Union(geometry)::geography) 
                FROM spatial_features 
                WHERE analysis_id = :analysis_id AND class_name = :cls_name
            """)
            area = db.execute(cls_query, {"analysis_id": analysis_id, "cls_name": cls_name}).scalar() or 0.0
            class_areas[cls_name] = area

        # 3. OSM Facility Counts
        osm_counts = {}
        for cat in ["hospital", "school", "police", "fire_station"]:
            # Distinct on osm_id to prevent any duplicate nodes inflating count
            count_query = text("""
                SELECT COUNT(DISTINCT osm_id) 
                FROM osm_features 
                WHERE analysis_id = :analysis_id AND category = :cat
            """)
            count = db.execute(count_query, {"analysis_id": analysis_id, "cat": cat}).scalar() or 0
            osm_counts[cat] = count

        # Calculate Percentages
        def calc_pct(area: float) -> float:
            return min(round((area / total_area_sq_m) * 100, 2), 100.0)

        road_coverage_pct = calc_pct(class_areas["road"])
        building_coverage_pct = calc_pct(class_areas["building"])
        tree_cover_pct = calc_pct(class_areas["tree_cover"])
        water_cover_pct = calc_pct(class_areas["water"])
        barren_cover_pct = calc_pct(class_areas["barren_land"])
        agriculture_cover_pct = calc_pct(class_areas["agriculture"])

        # Fetch benchmarks for scoring
        benchmarks = db.execute(text("SELECT indicator, target_value FROM benchmark_definitions")).fetchall()
        bm_targets = {b[0]: b[1] for b in benchmarks}

        # Initialize normalized metrics
        hospitals_per_1000 = None
        schools_per_1000 = None
        
        # Scoring logic
        infra_score = None
        component_scores = {}
        required_targets = {
            "tree_cover_pct": bm_targets.get("tree_cover_pct"),
            "road_coverage_pct": bm_targets.get("road_coverage_pct"),
            "hospitals_per_1000": bm_targets.get("hospitals_per_1000"),
            "schools_per_1000": bm_targets.get("schools_per_1000"),
        }
        
        # If population is missing, per-capita metrics and score will be None (Unavailable)
        if population_count and population_count > 0 and all(target is not None for target in required_targets.values()):
            hospitals_per_1000 = round((osm_counts["hospital"] / population_count) * 1000, 3)
            schools_per_1000 = round((osm_counts["school"] / population_count) * 1000, 3)
            
            # Simple score: 
            # 1. Tree Cover (target 15%)
            # 2. Road Coverage (target 5% coverage - substitute for density)
            # 3. Hospitals per 1k (target 0.5)
            # 4. Schools per 1k (target 1.0)
            target_tree = required_targets["tree_cover_pct"]
            target_road = required_targets["road_coverage_pct"]
            target_hosp = required_targets["hospitals_per_1000"]
            target_sch = required_targets["schools_per_1000"]
            
            s_tree = min((tree_cover_pct / target_tree) * 25, 25.0)
            s_road = min((road_coverage_pct / target_road) * 25, 25.0)
            s_hosp = min((hospitals_per_1000 / target_hosp) * 25, 25.0)
            s_sch = min((schools_per_1000 / target_sch) * 25, 25.0)
            
            infra_score = round(s_tree + s_road + s_hosp + s_sch, 1)
            
            component_scores = {
                "tree_cover": {"value": tree_cover_pct, "target": target_tree, "score": round(s_tree, 1), "max": 25, "unit": "%", "source": "benchmark_definitions"},
                "road_coverage": {"value": road_coverage_pct, "target": target_road, "score": round(s_road, 1), "max": 25, "unit": "%", "source": "benchmark_definitions"},
                "hospitals": {"value": hospitals_per_1000, "target": target_hosp, "score": round(s_hosp, 1), "max": 25, "unit": "per 1,000 people", "source": "benchmark_definitions"},
                "schools": {"value": schools_per_1000, "target": target_sch, "score": round(s_sch, 1), "max": 25, "unit": "per 1,000 people", "source": "benchmark_definitions"}
            }

        return {
            "population_count": population_count,
            "population_source": population_source,
            "population_date": population_date,
            "analysis_area_sq_km": round(total_area_sq_km, 3),
            
            "road_area_sq_m": round(class_areas["road"], 2),
            "road_coverage_pct": road_coverage_pct,
            
            "building_area_sq_m": round(class_areas["building"], 2),
            "building_coverage_pct": building_coverage_pct,
            
            "tree_area_sq_m": round(class_areas["tree_cover"], 2),
            "tree_cover_pct": tree_cover_pct,
            
            "water_area_sq_m": round(class_areas["water"], 2),
            "water_cover_pct": water_cover_pct,
            
            "barren_area_sq_m": round(class_areas["barren_land"], 2),
            "barren_cover_pct": barren_cover_pct,
            "agriculture_area_sq_m": round(class_areas["agriculture"], 2),
            "agriculture_cover_pct": agriculture_cover_pct,
            
            "hospital_count": osm_counts["hospital"],
            "school_count": osm_counts["school"],
            "police_count": osm_counts["police"],
            "fire_station_count": osm_counts["fire_station"],
            
            "hospitals_per_1000": hospitals_per_1000,
            "schools_per_1000": schools_per_1000,
            
            "infrastructure_score": infra_score,
            "component_scores": component_scores,
            "formula_version": "1.1",
            
            "calculated_at": datetime.now(timezone.utc)
        }
