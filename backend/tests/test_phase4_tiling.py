import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np


class Phase4TilingSmokeTests(unittest.TestCase):
    def test_compute_tiles_covers_image(self):
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "dev-test-secret",
            "DATABASE_URL": "sqlite:///./test_phase4.db",
            "MINIO_ROOT_USER": "test-minio",
            "MINIO_ROOT_PASSWORD": "test-minio-secret",
        }, clear=False):
            from app.services.tiling_service import TilingService

            with patch.object(TilingService, "TILE_SIZE", 256), patch.object(TilingService, "OVERLAP", 0.25):
                tiles = TilingService.compute_tiles(640, 480)

        self.assertGreater(len(tiles), 1)
        self.assertEqual(tiles[0].x, 0)
        self.assertEqual(tiles[0].y, 0)

        max_x = max(tile.x + tile.width for tile in tiles)
        max_y = max(tile.y + tile.height for tile in tiles)
        self.assertGreaterEqual(max_x, 640)
        self.assertGreaterEqual(max_y, 480)

    def test_run_ensemble_on_tiles_returns_full_probability_map(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "tiling_input.png"
            image = np.zeros((600, 700, 3), dtype=np.uint8)
            image[:, :] = (90, 140, 190)
            cv2.imwrite(str(image_path), image)

            project_classes = ["road", "building", "tree_cover"]

            def _fake_prob_map(tile_path: str, classes):
                return np.full((256, 256, len(classes)), 1.0 / len(classes), dtype=np.float32)

            with patch.dict(os.environ, {
                "ENVIRONMENT": "development",
                "SECRET_KEY": "dev-test-secret",
                "DATABASE_URL": "sqlite:///./test_phase4.db",
                "MINIO_ROOT_USER": "test-minio",
                "MINIO_ROOT_PASSWORD": "test-minio-secret",
            }, clear=False):
                from app.services.tiling_service import TilingService

                with patch.object(TilingService, "TILE_SIZE", 256), \
                     patch.object(TilingService, "OVERLAP", 0.25), \
                     patch("app.services.tiling_service.ModelService.generate_fused_probability_map", side_effect=_fake_prob_map):
                    fused, tiles = TilingService.run_ensemble_on_tiles(str(image_path), 600, 700, project_classes)

            self.assertEqual(fused.shape, (600, 700, len(project_classes)))
            self.assertGreater(len(tiles), 1)
            self.assertTrue(np.allclose(np.sum(fused, axis=-1), 1.0, atol=1e-5))


if __name__ == "__main__":
    unittest.main()