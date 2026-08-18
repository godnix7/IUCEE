import json
import time
import requests
from typing import List, Dict, Any, Tuple
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.ops import polygonize
from app.core.config import settings

class OSMServiceException(Exception):
    pass

class OSMService:
    CATEGORY_MAPPING = {
        "hospital": "hospital",
        "school": "school",
        "police": "police",
        "fire_station": "fire_station"
    }

    @classmethod
    def fetch_osm_enrichment(
        cls, bounds: Tuple[float, float, float, float]
    ) -> Tuple[List[Dict[str, Any]], str, str, List[str], List[str]]:
        """
        Query OpenStreetMap Overpass API for POIs within the given geographic bounds.
        Returns: (features, status, error_message, categories_requested, categories_completed)
        """
        if not settings.OSM_ENABLED:
            return [], "failed", "OSM enrichment disabled", list(cls.CATEGORY_MAPPING.values()), []

        min_lon, min_lat, max_lon, max_lat = bounds
        # Overpass expects (south, west, north, east)
        south, west, north, east = min_lat, min_lon, max_lat, max_lon

        # We request exactly the required categories
        amenities = "hospital|school|police|fire_station"
        
        overpass_query = f"""[out:json][timeout:{settings.OSM_REQUEST_TIMEOUT}];
(
  node["amenity"~"{amenities}"]({south},{west},{north},{east});
  way["amenity"~"{amenities}"]({south},{west},{north},{east});
  relation["amenity"~"{amenities}"]({south},{west},{north},{east});
);
out body geom;"""

        url = settings.OVERPASS_URL
        max_retries = settings.OSM_MAX_RETRIES
        timeout = settings.OSM_REQUEST_TIMEOUT + 5 # slight buffer over the overpass timeout
        
        attempt = 0
        response_data = None
        error_msg = None

        headers = {
            "User-Agent": "UrbanSense/1.0 (Contact: admin@urbansense.ai)",
            "Accept": "application/json"
        }
        
        print(f"[OSMService] Requesting Overpass URL: {url} with query:")
        print(overpass_query)

        while attempt <= max_retries:
            try:
                response = requests.post(url, data={"data": overpass_query}, headers=headers, timeout=timeout)
                response.raise_for_status()
                response_data = response.json()
                break
            except Exception as e:
                error_msg = str(e)
                print(f"[OSMService] Query failed: {error_msg}")
                print(f"[OSMService] Query was: {overpass_query}")
                attempt += 1
                if attempt <= max_retries:
                    time.sleep(2)
        
        requested = list(set(cls.CATEGORY_MAPPING.values()))
        
        if not response_data:
            return [], "failed", f"Overpass query failed after {max_retries} retries: {error_msg}", requested, []

        elements = response_data.get("elements", [])
        
        features = []
        completed_categories = set()

        for el in elements:
            osm_type = el.get("type")
            osm_id = el.get("id")
            tags = el.get("tags", {})
            
            amenity = tags.get("amenity")
            if not amenity or amenity not in cls.CATEGORY_MAPPING:
                continue
                
            category = cls.CATEGORY_MAPPING[amenity]
            completed_categories.add(category)
            name = tags.get("name", None)

            geometry = None
            
            try:
                if osm_type == "node":
                    lat, lon = el.get("lat"), el.get("lon")
                    if lat and lon:
                        geometry = Point(lon, lat)
                
                elif osm_type == "way":
                    geom_nodes = el.get("geometry", [])
                    coords = [(n["lon"], n["lat"]) for n in geom_nodes if "lon" in n and "lat" in n]
                    if len(coords) >= 4 and coords[0] == coords[-1]:
                        # Closed way usually implies a polygon for amenities
                        geometry = Polygon(coords)
                    elif len(coords) >= 2:
                        geometry = LineString(coords)
                        
                elif osm_type == "relation":
                    members = el.get("members", [])
                    lines = []
                    for mem in members:
                        if mem.get("type") == "way":
                            geom_nodes = mem.get("geometry", [])
                            coords = [(n["lon"], n["lat"]) for n in geom_nodes if "lon" in n and "lat" in n]
                            if len(coords) >= 2:
                                lines.append(LineString(coords))
                    
                    if lines:
                        # Try to polygonize the lines for complex relation multipolygons
                        polys = list(polygonize(lines))
                        if len(polys) == 1:
                            geometry = polys[0]
                        elif len(polys) > 1:
                            geometry = MultiPolygon(polys)
                        else:
                            # Fallback to multi-linestring if it doesn't form a closed polygon
                            geometry = lines[0] if len(lines) == 1 else MultiPolygon([Polygon(l) for l in lines if l.is_closed] or [])
                            if geometry.is_empty:
                                continue
            except Exception as e:
                # If geometry parsing fails for a complex object, skip it
                print(f"[OSMService] Warning: Failed to parse geometry for {osm_type} {osm_id}: {e}")
                continue

            if not geometry or geometry.is_empty:
                continue
                
            # Make sure it's valid
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
            
            features.append({
                "osm_type": osm_type,
                "osm_id": osm_id,
                "category": category,
                "name": name,
                "tags": tags,
                "geometry": geometry,
                "source": "openstreetmap"
            })
            
        status = "completed" if not error_msg else "failed"
        return features, status, error_msg, requested, list(completed_categories)
