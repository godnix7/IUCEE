import requests
from typing import List, Dict, Any, Tuple
from app.core.config import settings

class OSMService:
    @classmethod
    def fetch_osm_enrichment(
        cls, bounds: Tuple[float, float, float, float]
    ) -> List[Dict[str, Any]]:
        """
        Query OpenStreetMap Overpass API for POIs (Hospitals, Schools, Slums / Informal Settlements)
        within bounding box [min_lon, min_lat, max_lon, max_lat].
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        south, west, north, east = min_lat, min_lon, max_lat, max_lon

        overpass_query = f"""
        [out:json][timeout:15];
        (
          node["amenity"="hospital"]({south},{west},{north},{east});
          way["amenity"="hospital"]({south},{west},{north},{east});
          node["amenity"="school"]({south},{west},{north},{east});
          way["amenity"="school"]({south},{west},{north},{east});
          node["building"="hospital"]({south},{west},{north},{east});
          node["building"="school"]({south},{west},{north},{east});
          way["landuse"="informal_settlement"]({south},{west},{north},{east});
          way["residential"="slum"]({south},{west},{north},{east});
        );
        out body center;
        """

        features = []
        try:
            response = requests.post(
                settings.OVERPASS_API_URL,
                data={"data": overpass_query},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])

                hospital_polys = []
                school_polys = []
                slum_polys = []

                for el in elements:
                    tags = el.get("tags", {})
                    lat = el.get("lat") or el.get("center", {}).get("lat")
                    lon = el.get("lon") or el.get("center", {}).get("lon")

                    if not lat or not lon:
                        continue

                    # Create small buffer polygon around lat/lon point (~30m radius)
                    delta = 0.0003
                    poly = [
                        [round(lon - delta, 6), round(lat - delta, 6)],
                        [round(lon + delta, 6), round(lat - delta, 6)],
                        [round(lon + delta, 6), round(lat + delta, 6)],
                        [round(lon - delta, 6), round(lat + delta, 6)],
                        [round(lon - delta, 6), round(lat - delta, 6)]
                    ]

                    amenity = tags.get("amenity", "")
                    building = tags.get("building", "")
                    landuse = tags.get("landuse", "")
                    residential = tags.get("residential", "")

                    if amenity in ["hospital", "clinic"] or building == "hospital":
                        hospital_polys.append((poly, tags.get("name", "Hospital")))
                    elif amenity in ["school", "college", "university"] or building == "school":
                        school_polys.append((poly, tags.get("name", "School")))
                    elif landuse == "informal_settlement" or residential == "slum":
                        slum_polys.append((poly, tags.get("name", "Informal Settlement")))

                if hospital_polys:
                    features.append({
                        "class_name": "hospital",
                        "source": "osm_layer",
                        "confidence": 1.0,
                        "area_sq_meters": len(hospital_polys) * 3500.0,
                        "feature_count": len(hospital_polys),
                        "geometry_json": {
                            "type": "MultiPolygon",
                            "coordinates": [[item[0]] for item in hospital_polys]
                        },
                        "properties": {"names": [item[1] for item in hospital_polys]}
                    })

                if school_polys:
                    features.append({
                        "class_name": "school",
                        "source": "osm_layer",
                        "confidence": 1.0,
                        "area_sq_meters": len(school_polys) * 4500.0,
                        "feature_count": len(school_polys),
                        "geometry_json": {
                            "type": "MultiPolygon",
                            "coordinates": [[item[0]] for item in school_polys]
                        },
                        "properties": {"names": [item[1] for item in school_polys]}
                    })

                if slum_polys:
                    features.append({
                        "class_name": "slum",
                        "source": "osm_layer",
                        "confidence": 0.9,
                        "area_sq_meters": len(slum_polys) * 12000.0,
                        "feature_count": len(slum_polys),
                        "geometry_json": {
                            "type": "MultiPolygon",
                            "coordinates": [[item[0]] for item in slum_polys]
                        },
                        "properties": {"names": [item[1] for item in slum_polys]}
                    })

        except Exception as e:
            print(f"[OSMService] Error fetching Overpass OSM data: {e}")

        return features
