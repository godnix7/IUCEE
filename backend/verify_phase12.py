import io
import os
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from app.api.deps import get_current_user, require_spatial_db, get_db
from app.api.v1 import inference as inference_module
from app.core.config import settings
from app.models import Project


def _make_png_bytes(width: int = 8, height: int = 8, color=(32, 96, 160)) -> bytes:
    image = PILImage.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_tiff_bytes(width: int = 8, height: int = 8, color=(32, 160, 96)) -> bytes:
    image = PILImage.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="TIFF")
    return buffer.getvalue()


def _seed_project() -> int:
    return 1


class _FakeQuery:
    def __init__(self, model, session):
        self.model = model
        self.session = session

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.model is Project:
            return self.session.project
        return None


class _FakeSession:
    def __init__(self):
        self.project = Project(id=1, name="Phase 12 Validation Project", description="Upload validation test project")
        self._next_id = 100

    def query(self, model):
        return _FakeQuery(model, self)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def verify_phase12() -> bool:
    print("--- PHASE 12 FILE VALIDATION VERIFICATION ---")

    test_app = FastAPI()
    test_app.include_router(inference_module.router, prefix="/api/v1/inference")
    test_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin", is_active=True)
    test_app.dependency_overrides[require_spatial_db] = lambda: None

    original_upload_file = inference_module.StorageService.upload_file
    original_delay = inference_module.process_imagery_analysis.delay
    original_read_raster_metadata = inference_module.GeoService.read_raster_metadata
    original_validate_crs = inference_module.GeoService.validate_crs
    original_raster_bounds = inference_module.GeoService.raster_bounds
    original_max_upload_size_mb = settings.MAX_UPLOAD_SIZE_MB

    project_id = _seed_project()
    fake_session = _FakeSession()
    test_app.dependency_overrides[get_db] = lambda: fake_session
    client = TestClient(test_app)

    try:
        inference_module.StorageService.upload_file = lambda file_path, object_name: object_name
        inference_module.process_imagery_analysis.delay = lambda *args, **kwargs: SimpleNamespace(id="fake-task")
        inference_module.GeoService.read_raster_metadata = lambda temp_path: {
            "crs": "EPSG:3857",
            "width": 8,
            "height": 8,
            "resolution": (0.5, -0.5),
        }
        inference_module.GeoService.validate_crs = lambda crs: "EPSG:3857"
        inference_module.GeoService.raster_bounds = lambda temp_path: SimpleNamespace(
            bounds=(77.55, 12.95, 77.65, 13.05),
            wkt="POLYGON ((77.55 12.95, 77.65 12.95, 77.65 13.05, 77.55 13.05, 77.55 12.95))",
        )

        print("1. Accepting a valid PNG upload...")
        valid_png = _make_png_bytes()
        response = client.post(
            "/api/v1/inference/upload",
            data={"project_id": str(project_id)},
            files={"file": ("sample.png", valid_png, "image/png")},
        )
        if response.status_code != 200:
            print(f"FAILED: expected 200 for valid upload, got {response.status_code}: {response.text}")
            return False

        payload = response.json()
        if payload.get("status") != "queued" or not payload.get("analysis_id") or not payload.get("job_id"):
            print(f"FAILED: unexpected upload payload: {payload}")
            return False
        print(f"   PASS: analysis_id={payload['analysis_id']}, job_id={payload['job_id']}")

        print("2. Rejecting MIME-type mismatch...")
        bad_mime = client.post(
            "/api/v1/inference/upload",
            data={"project_id": str(project_id)},
            files={"file": ("sample.png", valid_png, "text/plain")},
        )
        if bad_mime.status_code != 400 or "Unsupported file type" not in bad_mime.text:
            print(f"FAILED: expected 400 MIME rejection, got {bad_mime.status_code}: {bad_mime.text}")
            return False
        print("   PASS: MIME mismatch rejected")

        print("3. Rejecting oversized upload...")
        settings.MAX_UPLOAD_SIZE_MB = 0
        oversized = client.post(
            "/api/v1/inference/upload",
            data={"project_id": str(project_id)},
            files={"file": ("sample.png", valid_png, "image/png")},
        )
        if oversized.status_code != 400 or "File too large" not in oversized.text:
            print(f"FAILED: expected 400 oversize rejection, got {oversized.status_code}: {oversized.text}")
            return False
        print("   PASS: oversized file rejected")

        print("4. Accepting a valid GeoTIFF upload...")
        settings.MAX_UPLOAD_SIZE_MB = original_max_upload_size_mb
        valid_tiff = _make_tiff_bytes()
        geotiff_response = client.post(
            "/api/v1/inference/upload",
            data={"project_id": str(project_id)},
            files={"file": ("sample.tif", valid_tiff, "image/tiff")},
        )
        if geotiff_response.status_code != 200:
            print(f"FAILED: expected 200 for valid GeoTIFF upload, got {geotiff_response.status_code}: {geotiff_response.text}")
            return False

        geotiff_payload = geotiff_response.json()
        if geotiff_payload.get("status") != "queued" or not geotiff_payload.get("analysis_id") or not geotiff_payload.get("job_id"):
            print(f"FAILED: unexpected GeoTIFF payload: {geotiff_payload}")
            return False
        print(f"   PASS: GeoTIFF analysis_id={geotiff_payload['analysis_id']}, job_id={geotiff_payload['job_id']}")

        print("5. Rejecting GeoTIFF MIME mismatch...")
        bad_geotiff_mime = client.post(
            "/api/v1/inference/upload",
            data={"project_id": str(project_id)},
            files={"file": ("sample.tif", valid_tiff, "image/png")},
        )
        if bad_geotiff_mime.status_code != 400 or "Unsupported file type" not in bad_geotiff_mime.text:
            print(f"FAILED: expected 400 GeoTIFF MIME rejection, got {bad_geotiff_mime.status_code}: {bad_geotiff_mime.text}")
            return False
        print("   PASS: GeoTIFF MIME mismatch rejected")

        print("\n--- PHASE 12 VERIFICATION REPORT ---")
        print("Upload validation: PASS")
        print("MIME guard: PASS")
        print("Size guard: PASS")
        print("GeoTIFF branch: PASS")
        print("Result: PHASE 12 FILE VALIDATION APPROVED")
        return True
    finally:
        settings.MAX_UPLOAD_SIZE_MB = original_max_upload_size_mb
        inference_module.StorageService.upload_file = original_upload_file
        inference_module.process_imagery_analysis.delay = original_delay
        inference_module.GeoService.read_raster_metadata = original_read_raster_metadata
        inference_module.GeoService.validate_crs = original_validate_crs
        inference_module.GeoService.raster_bounds = original_raster_bounds
        test_app.dependency_overrides.clear()


if __name__ == "__main__":
    success = verify_phase12()
    sys.exit(0 if success else 1)