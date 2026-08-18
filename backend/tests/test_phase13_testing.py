import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _make_png_bytes(width: int = 8, height: int = 8, color=(32, 96, 160)) -> bytes:
    image = PILImage.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeQuery:
    def __init__(self, model, session):
        self.model = model
        self.session = session

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.session.project if self.model.__name__ == "Project" else None


class _FakeSession:
    def __init__(self):
        from app.models import Project

        self.project = Project(id=1, name="Phase 13 Testing Project", description="Smoke test project")
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


class Phase13TestingSmokeTests(unittest.TestCase):
    def test_production_config_rejects_missing_credentials(self):
        env = os.environ.copy()
        env["ENVIRONMENT"] = "production"
        env["DATABASE_URL"] = "postgresql+psycopg://user:@db:5432/app"
        env["SECRET_KEY"] = "x"
        env.pop("MINIO_ROOT_USER", None)
        env.pop("MINIO_ROOT_PASSWORD", None)

        proc = subprocess.run(
            [sys.executable, "-c", "from app.core.config import settings"],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("MINIO_ROOT_USER is required in production", proc.stderr)
        self.assertIn("MINIO_ROOT_PASSWORD is required in production", proc.stderr)

    def test_upload_validation_smoke(self):
        env_patch = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "dev-test-secret",
            "DATABASE_URL": "sqlite:///./test_phase13.db",
            "MINIO_ROOT_USER": "test-minio",
            "MINIO_ROOT_PASSWORD": "test-minio-secret",
        }

        with patch.dict(os.environ, env_patch, clear=False):
            from app.api.deps import get_current_user, get_db, require_spatial_db
            from app.api.v1 import inference as inference_module

            test_app = FastAPI()
            test_app.include_router(inference_module.router, prefix="/api/v1/inference")
            test_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin", is_active=True)
            test_app.dependency_overrides[require_spatial_db] = lambda: None
            test_app.dependency_overrides[get_db] = lambda: _FakeSession()

            original_upload_file = inference_module.StorageService.upload_file
            original_delay = inference_module.process_imagery_analysis.delay
            original_read_raster_metadata = inference_module.GeoService.read_raster_metadata
            original_validate_crs = inference_module.GeoService.validate_crs
            original_raster_bounds = inference_module.GeoService.raster_bounds

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

                client = TestClient(test_app)
                valid_png = _make_png_bytes()

                ok = client.post(
                    "/api/v1/inference/upload",
                    data={"project_id": "1"},
                    files={"file": ("sample.png", valid_png, "image/png")},
                )
                self.assertEqual(ok.status_code, 200)
                self.assertEqual(ok.json()["status"], "queued")

                bad_mime = client.post(
                    "/api/v1/inference/upload",
                    data={"project_id": "1"},
                    files={"file": ("sample.png", valid_png, "text/plain")},
                )
                self.assertEqual(bad_mime.status_code, 400)
                self.assertIn("Unsupported file type", bad_mime.text)

                geotiff = client.post(
                    "/api/v1/inference/upload",
                    data={"project_id": "1"},
                    files={"file": ("sample.tif", valid_png, "image/tiff")},
                )
                self.assertEqual(geotiff.status_code, 200)
            finally:
                inference_module.StorageService.upload_file = original_upload_file
                inference_module.process_imagery_analysis.delay = original_delay
                inference_module.GeoService.read_raster_metadata = original_read_raster_metadata
                inference_module.GeoService.validate_crs = original_validate_crs
                inference_module.GeoService.raster_bounds = original_raster_bounds
                test_app.dependency_overrides.clear()

    def test_postgis_startup_probe(self):
        env_patch = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "dev-test-secret",
            "DATABASE_URL": "sqlite:///./test_phase13.db",
            "MINIO_ROOT_USER": "test-minio",
            "MINIO_ROOT_PASSWORD": "test-minio-secret",
        }

        with patch.dict(os.environ, env_patch, clear=False):
            from app.core import database

            original_env = database.settings.ENVIRONMENT
            original_url = database.settings.DATABASE_URL
            original_session_local = database.SessionLocal

            class _PassSession:
                def execute(self, stmt):
                    return None

                def close(self):
                    return None

            class _FailSession:
                def execute(self, stmt):
                    raise RuntimeError("PostGIS unavailable")

                def close(self):
                    return None

            try:
                database.settings.ENVIRONMENT = "production"
                database.settings.DATABASE_URL = "postgresql+psycopg://user:pass@db:5432/app"
                database.SessionLocal = lambda: _PassSession()
                database._validate_postgis_available()

                database.SessionLocal = lambda: _FailSession()
                with self.assertRaisesRegex(ValueError, "working PostGIS database"):
                    database._validate_postgis_available()
            finally:
                database.settings.ENVIRONMENT = original_env
                database.settings.DATABASE_URL = original_url
                database.SessionLocal = original_session_local


if __name__ == "__main__":
    unittest.main()