import json
import os
from pydantic_settings import BaseSettings

_ONTOLOGY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ontology",
    "aerial_infrastructure.json",
)


def load_aerial_ontology() -> list:
    """Load class ontology from JSON so new classes require no code changes."""
    path = os.getenv("AERIAL_ONTOLOGY_PATH", _ONTOLOGY_PATH)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Aerial Infrastructure Dataset Platform"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'sql_app.db')}"
    )

    # Storage settings
    DATA_DIR: str = os.getenv(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    )
    THUMBNAIL_SIZE: tuple = (256, 256)

    # Tiling
    TILE_SIZE: int = 1024
    TILE_OVERLAP: float = 0.20

    # Processing settings
    MAX_RETRIES: int = 3
    SUPPORTED_EXTENSIONS: set = {
        ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".geotiff", ".bmp", ".webp"
    }
    USE_REAL_MODELS: bool = os.getenv("USE_REAL_MODELS", "true").lower() == "true"
    MAX_CONCURRENCY: int = int(os.getenv("MAX_CONCURRENCY", "4"))

    # Remote H200 inference (optional)
    REMOTE_INFERENCE_URL: str = os.getenv("REMOTE_INFERENCE_URL", "")
    REMOTE_INFERENCE_API_KEY: str = os.getenv("REMOTE_INFERENCE_API_KEY", "")

    PUBLIC_API_URL: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

    # Active learning
    CONFIDENCE_UNKNOWN_THRESHOLD: float = 0.60
    ACTIVE_LEARNING_PENALTY: float = 0.15
    MIN_SAMPLES_FOR_PENALTY: int = 5

    class Config:
        case_sensitive = True
        env_file = ".env"

    @property
    def DEFAULT_AERIAL_CLASSES(self) -> list:
        loaded = load_aerial_ontology()
        if loaded:
            return loaded
        return [
            {"name": "road", "color": "#3b82f6", "shortcut_key": "1"},
            {"name": "building", "color": "#ef4444", "shortcut_key": "2"},
            {"name": "tree_cover", "color": "#22c55e", "shortcut_key": "3"},
        ]


settings = Settings()
