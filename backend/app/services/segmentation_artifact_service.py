import os
from typing import List

import cv2
import numpy as np

from app.core.config import settings
from app.models import Image


class SegmentationArtifactService:
    @classmethod
    def save_mask_overlay(
        cls,
        project_id: int,
        image: Image,
        label_map: np.ndarray,
        project_classes: List[str],
    ) -> str:
        overlay_dir = os.path.join(settings.DATA_DIR, "masks", str(project_id))
        os.makedirs(overlay_dir, exist_ok=True)
        overlay_path = os.path.join(overlay_dir, f"{image.id}_overlay.png")

        palette = np.array(
            [
                [59, 130, 246],
                [239, 68, 68],
                [245, 158, 11],
                [220, 38, 38],
                [234, 179, 8],
                [6, 182, 212],
                [14, 165, 233],
                [34, 197, 94],
                [168, 85, 247],
                [249, 115, 22],
                [139, 92, 246],
                [99, 102, 241],
                [253, 224, 71],
                [148, 163, 184],
                [217, 119, 6],
                [51, 65, 85],
                [236, 72, 153],
            ],
            dtype=np.uint8,
        )

        color_map = np.zeros((label_map.shape[0], label_map.shape[1], 3), dtype=np.uint8)
        for idx in range(min(len(project_classes), len(palette))):
            color_map[label_map == idx] = palette[idx]

        cv2.imwrite(overlay_path, color_map)
        image.mask_path = overlay_path
        return overlay_path

    @classmethod
    def save_confidence_map(cls, project_id: int, image: Image, confidence_map: np.ndarray) -> str:
        conf_dir = os.path.join(settings.DATA_DIR, "confidence", str(project_id))
        os.makedirs(conf_dir, exist_ok=True)
        conf_path = os.path.join(conf_dir, f"{image.id}_confidence.npy")
        np.save(conf_path, confidence_map.astype(np.float32))
        image.confidence_map_path = conf_path
        return conf_path
