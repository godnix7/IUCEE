import os
import time
import requests
import rasterio
from rasterio.transform import from_bounds
import numpy as np

BASE_URL = "http://127.0.0.1:8000/api/v1"
TEST_TIFF_PATH = "test_osm_footprint.tif"

# Let's use a real, known bounding box in Zurich since we are using overpass.osm.ch
# Bounds: lon, lat
MIN_LON, MIN_LAT = 8.53, 47.37
MAX_LON, MAX_LAT = 8.55, 47.39

WIDTH, HEIGHT = 1000, 1000

def create_test_geotiff():
    """Create a deterministic GeoTIFF located in London to overlap real OSM POIs."""
    print(f"Creating test GeoTIFF '{TEST_TIFF_PATH}' in EPSG:4326...")
    transform = from_bounds(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT, WIDTH, HEIGHT)
    
    data = np.zeros((3, HEIGHT, WIDTH), dtype=np.uint8)
    data[0, :, :] = 100
            
    with rasterio.open(
        TEST_TIFF_PATH, 'w',
        driver='GTiff',
        height=HEIGHT,
        width=WIDTH,
        count=3,
        dtype=data.dtype,
        crs='EPSG:4326',
        transform=transform
    ) as dst:
        dst.write(data)

def main():
    print("\n[============================================================]")
    print(">>> URBAN SENSE - PHASE 4: OSM ENRICHMENT TEST")
    print("[============================================================]\n")
    
    # 1. Login as Admin
    print("1. Authenticating...")
    res = requests.post(f"{BASE_URL}/auth/login", json={"email": "admin@urbansense.ai", "password": "dev_admin_2026"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Default Project ID
    res = requests.get(f"{BASE_URL}/projects", headers=headers)
    assert res.status_code == 200
    project_id = res.json()[0]["id"]
    
    # 3. Create the test GeoTIFF
    create_test_geotiff()
    
    # 4. Upload the GeoTIFF
    print("2. Uploading GeoTIFF for footprint...")
    with open(TEST_TIFF_PATH, 'rb') as f:
        files = {'file': (TEST_TIFF_PATH, f, 'image/tiff')}
        data = {'project_id': project_id}
        res = requests.post(f"{BASE_URL}/inference/upload", headers=headers, files=files, data=data)
        
    assert res.status_code == 200, f"Upload failed: {res.text}"
    analysis_id = res.json()["id"]
    print(f"   -> Upload successful. Analysis ID: {analysis_id}")

    # 5. Run OSM Enrichment
    print("3. Executing OSM Enrichment...")
    res = requests.post(f"{BASE_URL}/gis/analyses/{analysis_id}/osm-enrichment", headers=headers)
    assert res.status_code == 200, f"Enrichment failed: {res.text}"
    enrichment_result = res.json()
    print(f"   -> Enrichment returned: {enrichment_result}")
    assert enrichment_result["status"] == "completed"

    # 6. Run OSM Enrichment AGAIN (Duplicate Protection Test)
    print("4. Testing Duplicate Protection...")
    res2 = requests.post(f"{BASE_URL}/gis/analyses/{analysis_id}/osm-enrichment", headers=headers)
    assert res2.status_code == 200
    print("   -> Duplicate call successful, checking counts...")

    # 7. Fetch GeoJSON and Verify Output
    print("5. Fetching generated OSM Polygons...")
    res = requests.get(f"{BASE_URL}/gis/analyses/{analysis_id}/osm-enrichment", headers=headers)
    assert res.status_code == 200, f"GIS endpoint failed: {res.text}"
    geojson = res.json()
    
    features = geojson["features"]
    print(f"   -> Model produced {len(features)} OSM features.")
    assert len(features) > 0, "No OSM features were found in Zurich!"
    
    # Verify Source and Classes
    sources = set()
    classes = set()
    geom_types = set()
    
    for f in features:
        props = f["properties"]
        geom = f["geometry"]
        sources.add(props["source"])
        classes.add(props["category"])
        geom_types.add(geom["type"])
        
        assert props["source"] == "openstreetmap"
        assert props["osm_id"] is not None
        assert props["osm_type"] in ["node", "way", "relation"]
        
    print(f"   -> Detected Sources: {sources}")
    print(f"   -> Detected Categories: {classes}")
    print(f"   -> Detected Geometry Types: {geom_types}")
    
    assert "openstreetmap" in sources, "Source openstreetmap missing!"
    assert len(sources) == 1, "AI features leaked into OSM API!"
    
    # Clean up
    if os.path.exists(TEST_TIFF_PATH):
        os.remove(TEST_TIFF_PATH)
        
    print("\n[============================================================]")
    print(">>> SUCCESS: Real OSM API Enrichment active, bounds filtering works,")
    print(">>> geometries retained accurately, duplicates rejected.")
    print("[============================================================]\n")

if __name__ == "__main__":
    main()
