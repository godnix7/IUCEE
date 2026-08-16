from typing import List, Dict, Any, Tuple
from app.models import SpatialFeature, UrbanBenchmark

class BenchmarkService:
    @classmethod
    def calculate_benchmarks(
        cls,
        features: List[SpatialFeature],
        bounds: Tuple[float, float, float, float],
        population_count: int = 1000
    ) -> Dict[str, Any]:
        """
        Calculate real urban metrics, infrastructure per 1,000 population, road density,
        tree coverage, and composite infrastructure index score.
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
            if cls_name in counts:
                counts[cls_name] += f.feature_count

        building_area = class_areas["building"]
        road_area = class_areas["road"]
        tree_area = class_areas["tree_cover"]
        water_area = class_areas["water"]

        # Calculate ratios and metrics
        building_coverage_pct = min(round((building_area / total_area_m2) * 100, 2), 100.0)
        tree_cover_pct = min(round((tree_area / total_area_m2) * 100, 2), 100.0)
        water_cover_pct = min(round((water_area / total_area_m2) * 100, 2), 100.0)
        built_up_ratio = min(round(((building_area + road_area) / total_area_m2), 3), 1.0)

        # Estimate road length from road area (avg road width ~ 8 meters)
        road_length_km = (road_area / 8.0) / 1000.0
        road_density_km_per_sqkm = round(road_length_km / total_area_km2, 2)

        pop_factor = max(population_count, 1)
        hospitals_per_10k = round((counts["hospital"] / pop_factor) * 10000, 2)
        schools_per_10k = round((counts["school"] / pop_factor) * 10000, 2)

        # Infrastructure Score Calculation (0 to 100 scale)
        # Weights: Tree Cover (20%), Road Density (20%), Public Infra (30%), Balanced Built-up (30%)
        tree_score = min(tree_cover_pct * 2.5, 20.0) # max 20 pts for 8% green cover
        road_score = min(road_density_km_per_sqkm * 2.0, 20.0) # max 20 pts for 10 km/km2
        public_score = min((hospitals_per_10k + schools_per_10k) * 5.0, 30.0) # max 30 pts
        built_score = min(built_up_ratio * 30.0, 30.0)

        total_infra_score = round(tree_score + road_score + public_score + built_score, 1)

        return {
            "population_count": population_count,
            "road_density_km_per_sqkm": road_density_km_per_sqkm,
            "building_coverage_pct": building_coverage_pct,
            "tree_cover_pct": tree_cover_pct,
            "water_cover_pct": water_cover_pct,
            "built_up_ratio": built_up_ratio,
            "hospitals_per_10k_pop": hospitals_per_10k,
            "schools_per_10k_pop": schools_per_10k,
            "infrastructure_score": min(total_infra_score, 100.0)
        }
