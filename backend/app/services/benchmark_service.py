from typing import List, Dict, Any, Tuple
from app.models import SpatialFeature

class BenchmarkService:
    @classmethod
    def calculate_benchmarks(
        cls,
        features: List[SpatialFeature],
        osm_features: List[Any], # List[OSMFeature]
        bounds: Tuple[float, float, float, float],
        population_count: int | None = None
    ) -> Dict[str, Any]:
        """
        Calculate real urban metrics, infrastructure per 1,000 population, road coverage,
        tree coverage, and a composite infrastructure index score.
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        lat_dist_m = abs(max_lat - min_lat) * 111000
        lon_dist_m = abs(max_lon - min_lon) * 111000 * 0.97 # approximate cos(lat)
        total_area_m2 = max(lat_dist_m * lon_dist_m, 10000.0) # minimum 10k sq meters
        total_area_km2 = total_area_m2 / 1000000.0

        # Sum areas and count features
        class_areas = {
            "road": 0.0,
            "building": 0.0,
            "tree_cover": 0.0,
            "water": 0.0,
            "agriculture": 0.0,
            "barren_land": 0.0,
            "hospital": 0.0,
            "school": 0.0,
            "slum": 0.0,
            "open_land": 0.0
        }
        counts = {
            "hospital": 0,
            "school": 0,
            "building": 0
        }

        for f in features:
            cls_name = f.class_name
            if cls_name in class_areas:
                class_areas[cls_name] += f.area_sq_meters
                
        for of in osm_features:
            cat_name = of.category
            if cat_name in counts:
                counts[cat_name] += 1

        building_area = class_areas["building"]
        road_area = class_areas["road"]
        tree_area = class_areas["tree_cover"]
        water_area = class_areas["water"]

        # Calculate ratios and metrics
        building_coverage_pct = min(round((building_area / total_area_m2) * 100, 2), 100.0)
        road_coverage_pct = min(round((road_area / total_area_m2) * 100, 2), 100.0)
        tree_cover_pct = min(round((tree_area / total_area_m2) * 100, 2), 100.0)
        water_cover_pct = min(round((water_area / total_area_m2) * 100, 2), 100.0)
        built_up_ratio = min(round(((building_area + road_area) / total_area_m2), 3), 1.0)

        hospitals_per_1000 = None
        schools_per_1000 = None
        public_score = 0.0
        if population_count and population_count > 0:
            pop_factor = population_count
            hospitals_per_1000 = round((counts["hospital"] / pop_factor) * 1000, 3)
            schools_per_1000 = round((counts["school"] / pop_factor) * 1000, 3)
            public_score = min((hospitals_per_1000 + schools_per_1000) * 10.0, 30.0)

        # Infrastructure Score Calculation (0 to 100 scale)
        # Weights: Tree Cover (20%), Public Infra (30%), Balanced Built-up (30%)
        tree_score = min(tree_cover_pct * 2.5, 20.0) # max 20 pts for 8% green cover
        built_score = min(built_up_ratio * 30.0, 30.0)

        total_infra_score = round(tree_score + public_score + built_score, 1) if population_count and population_count > 0 else None

        return {
            "population_count": population_count,
            "road_density_km_per_sqkm": None,
            "road_coverage_pct": road_coverage_pct,
            "building_coverage_pct": building_coverage_pct,
            "tree_cover_pct": tree_cover_pct,
            "water_cover_pct": water_cover_pct,
            "built_up_ratio": built_up_ratio,
            "hospitals_per_1000_pop": hospitals_per_1000,
            "schools_per_1000_pop": schools_per_1000,
            "hospitals_per_10k_pop": (round(hospitals_per_1000 * 10, 2) if hospitals_per_1000 is not None else None),
            "schools_per_10k_pop": (round(schools_per_1000 * 10, 2) if schools_per_1000 is not None else None),
            "infrastructure_score": total_infra_score
        }
