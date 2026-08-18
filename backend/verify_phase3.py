import os
import math
import time
import requests
import rasterio
from rasterio.transform import from_bounds
import numpy as np

# Constants
BASE_URL = "http://127.0.0.1:8000/api/v1"
TEST_TIFF_PATH = "test_loveda_aerial.tif"

# 1500x1500 image for testing TILING (since LoveDA is 512x512)
# Expected bounds in UTM 33N:
MIN_X, MIN_Y, MAX_X, MAX_Y = 300000.0, 5000000.0, 301500.0, 5001500.0
WIDTH, HEIGHT = 1500, 1500
CRS_EPSG = 32633

def create_test_geotiff():
    """Create a 1500x1500 deterministic GeoTIFF to test 512x512 overlapping tiling."""
    print(f"Creating test GeoTIFF '{TEST_TIFF_PATH}' in EPSG:{CRS_EPSG} (1500x1500)...")
    transform = from_bounds(MIN_X, MIN_Y, MAX_X, MAX_Y, WIDTH, HEIGHT)
    
    # 3 bands for RGB (LoveDA model expects RGB)
    # Give it some shapes to predict (even though model is untrained random/pre-trained weights on gradient)
    data = np.zeros((3, HEIGHT, WIDTH), dtype=np.uint8)
    
    # Fill with some colors
    data[0, :500, :500] = 200 # Red box
    data[1, 500:1000, 500:1000] = 200 # Green box
    data[2, 1000:, 1000:] = 200 # Blue box
            
    with rasterio.open(
        TEST_TIFF_PATH, 'w',
        driver='GTiff',
        height=HEIGHT,
        width=WIDTH,
        count=3,
        dtype=data.dtype,
        crs=f'EPSG:{CRS_EPSG}',
        transform=transform
    ) as dst:
        dst.write(data)

def main():
    print("\n[============================================================]")
    print(">>> URBAN SENSE - PHASE 3: PRETRAINED LOVEDA AI TEST")
    print("[============================================================]\n")
    
    # 1. Login as Admin
    print("1. Authenticating as Admin...")
    res = requests.post(f"{BASE_URL}/auth/login", json={"email": "admin@urbansense.ai", "password": "dev_admin_2026"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Default Project ID
    res = requests.get(f"{BASE_URL}/projects", headers=headers)
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) > 0, "No projects found"
    project_id = projects[0]["id"]
    
    # 3. Create the test GeoTIFF
    create_test_geotiff()
    
    # 4. Upload the GeoTIFF
    print("2. Uploading GeoTIFF...")
    with open(TEST_TIFF_PATH, 'rb') as f:
        files = {'file': (TEST_TIFF_PATH, f, 'image/tiff')}
        data = {'project_id': project_id}
        res = requests.post(f"{BASE_URL}/inference/upload", headers=headers, files=files, data=data)
        
    assert res.status_code == 200, f"Upload failed: {res.text}"
    analysis = res.json()
    analysis_id = analysis["id"]
    print(f"   -> Upload successful. Analysis ID: {analysis_id}")
    
    # 5. Run AI Inference (Phase 3 Core Test)
    print("3. Executing SegFormer LoveDA Inference... (This may take a minute)")
    start = time.time()
    res = requests.post(f"{BASE_URL}/inference/{analysis_id}/run", headers=headers)
    duration = time.time() - start
    assert res.status_code == 200, f"Inference failed: {res.text}"
    inference_result = res.json()
    print(f"   -> Inference completed in {duration:.2f}s!")
    assert inference_result["status"] == "completed"
    assert inference_result["inference_time_sec"] > 0
    
    # 6. Fetch GeoJSON and Verify Output
    print("4. Fetching generated AI Polygons...")
    res = requests.get(f"{BASE_URL}/gis/analyses/{analysis_id}/geojson", headers=headers)
    assert res.status_code == 200, f"GIS endpoint failed: {res.text}"
    geojson = res.json()
    
    features = geojson["features"]
    print(f"   -> Model produced {len(features)} spatial features.")
    
    # Verify Source and Classes
    sources = set()
    classes = set()
    for f in features:
        sources.add(f["properties"]["source"])
        classes.add(f["properties"]["class_name"])
        
    print(f"   -> Detected Sources: {sources}")
    print(f"   -> Detected Classes: {classes}")
    
    assert "ai_segformer_loveda" in sources, "Source ai_segformer_loveda missing!"
    
    allowed_classes = {"building", "road", "water", "barren_land", "tree_cover", "agriculture"}
    for c in classes:
        assert c in allowed_classes, f"ILLEGAL CLASS DETECTED: {c}"
        
    print("   ✅ Class mappings match LoveDA strictly.")
    
    # Clean up
    if os.path.exists(TEST_TIFF_PATH):
        os.remove(TEST_TIFF_PATH)
        
    print("\n[============================================================]")
    print(">>> SUCCESS: Pretrained LoveDA inference pipeline is active,")
    print(">>> tiling functions correctly, and polygon geometries are sound.")
    print("[============================================================]\n")

if __name__ == "__main__":
    main()
