import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Image, Project, ProjectClass


class ImportService:
    @staticmethod
    def compute_file_hash(abs_path: str, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def validate_image(abs_path: str) -> Tuple[bool, int, int, Optional[str]]:
        try:
            with PILImage.open(abs_path) as img:
                img.verify()
            with PILImage.open(abs_path) as img:
                w, h = img.size
                if w <= 0 or h <= 0:
                    return False, 0, 0, "Invalid dimensions"
                return True, w, h, None
        except Exception as exc:
            return False, 0, 0, str(exc)

    @staticmethod
    def create_thumbnail(project_id: int, image_id: int, abs_path: str) -> Optional[str]:
        thumb_dir = os.path.join(settings.DATA_DIR, "thumbnails", str(project_id))
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"{image_id}.jpg")

        try:
            with PILImage.open(abs_path) as img:
                img = img.convert("RGB")
                img.thumbnail(settings.THUMBNAIL_SIZE, PILImage.Resampling.LANCZOS)
                img.save(thumb_path, "JPEG", quality=85)
            return thumb_path
        except Exception as exc:
            print(f"Thumbnail generation failed for {abs_path}: {exc}")
            return None

    @classmethod
    def index_project_folder(
        cls,
        db: Session,
        project: Project,
        root_path: str,
        custom_classes: Optional[List[dict]] = None,
    ) -> Dict[str, int]:
        root_dir = Path(root_path)
        extensions = settings.SUPPORTED_EXTENSIONS

        class_source = custom_classes if custom_classes else settings.DEFAULT_AERIAL_CLASSES
        for class_def in class_source:
            db.add(
                ProjectClass(
                    project_id=project.id,
                    name=class_def["name"],
                    color=class_def.get("color", "#64748b"),
                    shortcut_key=class_def.get("shortcut_key"),
                )
            )
        db.flush()

        entries: List[dict] = []
        for dirpath, _, files in os.walk(root_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in extensions:
                    continue

                abs_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(abs_path, root_dir)
                is_valid, w, h, err = cls.validate_image(abs_path)
                file_hash = cls.compute_file_hash(abs_path) if is_valid else None

                entries.append(
                    {
                        "filename": file,
                        "relative_path": rel_path,
                        "absolute_path": abs_path,
                        "width": w,
                        "height": h,
                        "file_size_bytes": os.path.getsize(abs_path),
                        "file_hash": file_hash,
                        "is_corrupt": not is_valid,
                        "error": err,
                    }
                )

        hash_first_index: Dict[str, int] = {}
        for idx, entry in enumerate(entries):
            if entry["is_corrupt"] or not entry["file_hash"]:
                entry["is_duplicate"] = False
                entry["duplicate_of_index"] = None
                continue
            h = entry["file_hash"]
            if h in hash_first_index:
                entry["is_duplicate"] = True
                entry["duplicate_of_index"] = hash_first_index[h]
            else:
                hash_first_index[h] = idx
                entry["is_duplicate"] = False
                entry["duplicate_of_index"] = None

        stats = {"indexed": 0, "duplicates": 0, "corrupt": 0, "valid": 0}
        images: List[Image] = []

        for entry in entries:
            stats["indexed"] += 1
            if entry["is_corrupt"]:
                stats["corrupt"] += 1
                status = "failed"
            elif entry["is_duplicate"]:
                stats["duplicates"] += 1
                status = "pending"
            else:
                stats["valid"] += 1
                status = "pending"

            images.append(
                Image(
                    project_id=project.id,
                    filename=entry["filename"],
                    relative_path=entry["relative_path"],
                    absolute_path=entry["absolute_path"],
                    width=entry["width"],
                    height=entry["height"],
                    file_size_bytes=entry["file_size_bytes"],
                    file_hash=entry["file_hash"],
                    is_duplicate=entry["is_duplicate"],
                    is_corrupt=entry["is_corrupt"],
                    status=status,
                    review_status="manual_review" if entry["is_corrupt"] else "accepted",
                    rejection_reason=entry["error"] if entry["is_corrupt"] else None,
                )
            )

        if images:
            db.add_all(images)
            db.flush()

            for idx, entry in enumerate(entries):
                if entry.get("duplicate_of_index") is not None:
                    images[idx].duplicate_of_id = images[entry["duplicate_of_index"]].id

            for img in images:
                if not img.is_corrupt and not img.is_duplicate:
                    thumb = cls.create_thumbnail(project.id, img.id, img.absolute_path)
                    if thumb:
                        img.thumbnail_path = thumb

        db.commit()
        return stats
