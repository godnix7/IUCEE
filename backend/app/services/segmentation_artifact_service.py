import os
from typing import List, Optional

import cv2
import numpy as np

from app.core.config import settings
from app.models import Image


# High-contrast palette for classes without a project-defined color.
# Designed for maximum visual distinguishability on aerial imagery.
_DEFAULT_PALETTE = np.array(
    [
        [128,   0,   0],   # 0  - maroon
        [  0, 128,   0],   # 1  - dark green
        [128, 128,   0],   # 2  - olive
        [  0,   0, 128],   # 3  - navy
        [128,   0, 128],   # 4  - purple
        [  0, 128, 128],   # 5  - teal
        [128, 128, 128],   # 6  - gray
        [ 64,   0,   0],   # 7  - dark maroon
        [192,   0,   0],   # 8  - red
        [ 64, 128,   0],   # 9  - lime green
        [192, 128,   0],   # 10 - orange
        [ 64,   0, 128],   # 11 - indigo
        [192,   0, 128],   # 12 - magenta
        [ 64, 128, 128],   # 13 - steel
        [192, 128, 128],   # 14 - rose
        [  0,  64,   0],   # 15 - forest
        [128,  64,   0],   # 16 - brown
    ],
    dtype=np.uint8,
)


def _hex_to_bgr(hex_str: str) -> Optional[np.ndarray]:
    """Convert a hex color string (e.g. '#FF5733') to a BGR numpy array."""
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 6:
        try:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return np.array([b, g, r], dtype=np.uint8)
        except ValueError:
            return None
    return None


class SegmentationArtifactService:
    @classmethod
    def save_mask_overlay(
        cls,
        project_id: int,
        image: Image,
        label_map: np.ndarray,
        project_classes: List[str],
        class_colors: Optional[List[Optional[str]]] = None,
    ) -> str:
        """
        Save a Cityscapes-quality mask overlay:
        1. Raw color-coded semantic mask (for downstream)
        2. Semi-transparent overlay blended with the original image (for review)
        3. Class boundary contour lines drawn on top
        """
        overlay_dir = os.path.join(settings.DATA_DIR, "masks", str(project_id))
        os.makedirs(overlay_dir, exist_ok=True)

        # Build color palette: use project-defined colors first, fall back to default
        palette = np.zeros((len(project_classes), 3), dtype=np.uint8)
        for idx in range(len(project_classes)):
            color_set = False
            if class_colors and idx < len(class_colors) and class_colors[idx]:
                bgr = _hex_to_bgr(class_colors[idx])
                if bgr is not None:
                    palette[idx] = bgr
                    color_set = True
            if not color_set:
                palette[idx] = _DEFAULT_PALETTE[idx % len(_DEFAULT_PALETTE)]

        # ---- Raw Color Mask ----
        color_mask = np.zeros((label_map.shape[0], label_map.shape[1], 3), dtype=np.uint8)
        for idx in range(len(project_classes)):
            color_mask[label_map == idx] = palette[idx]

        raw_mask_path = os.path.join(overlay_dir, f"{image.id}_mask.png")
        cv2.imwrite(raw_mask_path, color_mask)

        # ---- RGBA Overlay with Contours ----
        # Create an RGBA image for the mask
        h, w = label_map.shape[:2]
        rgba_mask = np.zeros((h, w, 4), dtype=np.uint8)
        
        # Apply colors with 45% opacity (alpha = 115)
        for idx in range(len(project_classes)):
            mask = label_map == idx
            b, g, r = palette[idx]
            rgba_mask[mask] = [b, g, r, 115]

        overlay_path = os.path.join(overlay_dir, f"{image.id}_overlay.png")
        cv2.imwrite(overlay_path, rgba_mask)

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
