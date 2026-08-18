import os
import time
import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@urbansense.ai")
ADMIN_PASS = os.getenv("SEED_ADMIN_PASSWORD", "changeme_admin")

def run_verification():
    print(f"[{datetime.now().isoformat()}] Starting Production Verification...")
    start_time = time.time()
    
    # 1. Health Check
    try:
        res = requests.get("http://localhost:8000/health")
        if res.status_code == 200:
            print("✓ [PASS] Health check")
        else:
            print("✗ [FAIL] Health check")
            return False
    except Exception as e:
        print("✗ [FAIL] Health check connection:", e)
        return False

    # 2. Authentication
    session = requests.Session()
    res = session.post(f"{API_BASE}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    
    if res.status_code == 200:
        token = res.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        print("✓ [PASS] Authentication")
    else:
        print("✗ [FAIL] Authentication")
        return False
        
    # 3. Create Project
    res = session.post(f"{API_BASE}/projects", json={
        "name": "Production Verification Test",
        "description": "E2E Test Project"
    })
    
    if res.status_code == 200:
        project_id = res.json()["id"]
        print(f"✓ [PASS] Project Creation (ID: {project_id})")
    else:
        print("✗ [FAIL] Project Creation")
        return False

    # Note: Uploading and full AI processing via script requires a real GeoTIFF in the environment.
    # We will verify the Analytics and Reports endpoints using the Dashboard's most recent analysis.
    
    res = session.get(f"{API_BASE}/analytics/dashboard")
    if res.status_code == 200:
        print("✓ [PASS] Dashboard API")
        stats = res.json()
        analyses = stats.get("recent_analyses", [])
        if analyses:
            analysis_id = analyses[0]["id"]
            
            # Check Analytics
            res_analytics = session.get(f"{API_BASE}/analytics/analyses/{analysis_id}")
            if res_analytics.status_code == 200:
                print("✓ [PASS] Analytics Retrieval")
            else:
                print("✗ [FAIL] Analytics Retrieval")
                
            # Check PDF Report
            res_pdf = session.get(f"{API_BASE}/reports/analyses/{analysis_id}/pdf")
            if res_pdf.status_code == 200 and res_pdf.headers.get("content-type") == "application/pdf":
                print("✓ [PASS] PDF Generation")
            else:
                print("✗ [FAIL] PDF Generation")
                
            # Check CSV Export
            res_csv = session.get(f"{API_BASE}/reports/analyses/{analysis_id}/csv")
            if res_csv.status_code == 200 and res_csv.headers.get("content-type") == "text/csv; charset=utf-8":
                print("✓ [PASS] CSV Generation")
            else:
                print("✗ [FAIL] CSV Generation")
                
            # Check GeoJSON Export
            res_geojson = session.get(f"{API_BASE}/reports/analyses/{analysis_id}/geojson")
            if res_geojson.status_code == 200 and res_geojson.headers.get("content-type") == "application/geo+json":
                print("✓ [PASS] GeoJSON Generation")
            else:
                print("✗ [FAIL] GeoJSON Generation")
        else:
            print("⚠ [WARN] No recent analyses found to test reporting endpoints.")
    else:
        print("✗ [FAIL] Dashboard API")

    # Benchmarks API
    res = session.get(f"{API_BASE}/benchmarks")
    if res.status_code == 200:
        print("✓ [PASS] Benchmarks API Retrieval")
    else:
        print("✗ [FAIL] Benchmarks API Retrieval")
        
    duration = time.time() - start_time
    print(f"[{datetime.now().isoformat()}] Verification Complete in {duration:.2f} seconds.")
    return True

if __name__ == "__main__":
    run_verification()
