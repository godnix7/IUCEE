import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Pixel Annotation Studio"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
    
    # Storage settings
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    THUMBNAIL_SIZE: tuple = (256, 256)
    
    # Processing settings
    MAX_RETRIES: int = 3
    SUPPORTED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".geotiff", ".bmp", ".webp"}
    USE_REAL_MODELS: bool = os.getenv("USE_REAL_MODELS", "false").lower() == "true"
    MAX_CONCURRENCY: int = int(os.getenv("MAX_CONCURRENCY", "4"))
    
    # Label Studio settings
    LABEL_STUDIO_URL: str = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    LABEL_STUDIO_API_KEY: str = os.getenv("LABEL_STUDIO_API_KEY", "1234567890123456789012345678901234567890")

    class Config:
        case_sensitive = True
        env_file = ".env"

    DEFAULT_AERIAL_CLASSES: list = [
        {"name": "building_rooftop", "color": "#ef4444", "shortcut_key": "1"},
        {"name": "road", "color": "#3b82f6", "shortcut_key": "2"},
        {"name": "parking_lot", "color": "#8b5cf6", "shortcut_key": "3"},
        {"name": "vehicle", "color": "#eab308", "shortcut_key": "4"},
        {"name": "low_vegetation", "color": "#84cc16", "shortcut_key": "5"},
        {"name": "tree_canopy", "color": "#22c55e", "shortcut_key": "6"},
        {"name": "water", "color": "#0ea5e9", "shortcut_key": "7"},
        {"name": "bare_ground", "color": "#d97706", "shortcut_key": "8"},
        {"name": "shadow", "color": "#334155", "shortcut_key": "9"},
        {"name": "construction", "color": "#f97316", "shortcut_key": "0"},
        {"name": "sidewalk_path", "color": "#a855f7", "shortcut_key": "q"},
        {"name": "unknown", "color": "#ec4899", "shortcut_key": "u"},
    ]

settings = Settings()
