import json
import os
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ImageTile
from app.services.model_service import ModelService


@dataclass
class TileSpec:
    index: int
    x: int
    y: int
    width: int
    height: int


class TilingService:
    TILE_SIZE = settings.TILE_SIZE
    OVERLAP = settings.TILE_OVERLAP

    @classmethod
    def compute_tiles(cls, width: int, height: int) -> List[TileSpec]:
        tile_size = cls.TILE_SIZE
        stride = int(tile_size * (1.0 - cls.OVERLAP))

        if width <= tile_size and height <= tile_size:
            return [TileSpec(0, 0, 0, width, height)]

        tiles: List[TileSpec] = []
        idx = 0
        for y in range(0, height, stride):
            for x in range(0, width, stride):
                x2 = min(x + tile_size, width)
                y2 = min(y + tile_size, height)
                x1 = max(0, x2 - tile_size)
                y1 = max(0, y2 - tile_size)
                tiles.append(TileSpec(idx, x1, y1, x2 - x1, y2 - y1))
                idx += 1
        return tiles

    @classmethod
    def persist_tile_metadata(cls, db: Session, image_id: int, tiles: List[TileSpec]) -> None:
        db.query(ImageTile).filter(ImageTile.image_id == image_id).delete()
        for tile in tiles:
            db.add(
                ImageTile(
                    image_id=image_id,
                    tile_index=tile.index,
                    x=tile.x,
                    y=tile.y,
                    width=tile.width,
                    height=tile.height,
                    metadata_json=json.dumps(
                        {
                            "tile_size": cls.TILE_SIZE,
                            "overlap": cls.OVERLAP,
                            "parent_image_id": image_id,
                        }
                    ),
                )
            )

    @classmethod
    def run_ensemble_on_tiles(
        cls,
        image_path: str,
        orig_h: int,
        orig_w: int,
        project_classes: List[str],
    ) -> Tuple[np.ndarray, List[TileSpec]]:
        """
        Process each tile independently and merge probability maps with
        overlap-aware averaging. Returns fused (H, W, C) probability map.
        """
        num_classes = len(project_classes)
        tiles = cls.compute_tiles(orig_w, orig_h)
        fused_sum = np.zeros((orig_h, orig_w, num_classes), dtype=np.float64)
        weight_sum = np.zeros((orig_h, orig_w), dtype=np.float64)

        orig_img = cv2.imread(image_path)
        if orig_img is None:
            orig_img = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)

        temp_dir = os.path.join(settings.DATA_DIR, "tiles")
        os.makedirs(temp_dir, exist_ok=True)

        for tile in tiles:
            crop = orig_img[tile.y : tile.y + tile.height, tile.x : tile.x + tile.width]
            if crop.size == 0:
                continue

            tile_path = os.path.join(temp_dir, f"tile_{os.getpid()}_{tile.index}.png")
            cv2.imwrite(tile_path, crop)

            tile_probs = ModelService.generate_fused_probability_map(tile_path, project_classes)

            tile_probs = cv2.resize(
                tile_probs,
                (tile.width, tile.height),
                interpolation=cv2.INTER_LINEAR,
            )

            y1, y2 = tile.y, tile.y + tile.height
            x1, x2 = tile.x, tile.x + tile.width
            fused_sum[y1:y2, x1:x2] += tile_probs
            weight_sum[y1:y2, x1:x2] += 1.0

            try:
                os.remove(tile_path)
            except OSError:
                pass

        weight_sum = np.maximum(weight_sum, 1e-6)
        fused = fused_sum / weight_sum[..., np.newaxis]
        return fused.astype(np.float32), tiles
