import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "UrbanSense - AI Powered Urban Infrastructure Intelligence System"
    API_V1_STR: str = "/api/v1"
    
    # Database URL: default sqlite local DB, supports Postgres/PostGIS URL via env
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'urbansense.db')}"
    )

    # JWT Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "urbansense_super_secret_jwt_key_2026_gis_ai_infrastructure")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Storage settings
    DATA_DIR: str = os.getenv(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    )

    # AI Model settings
    PRETRAINED_SEGFORMER_MODEL: str = os.getenv("PRETRAINED_SEGFORMER_MODEL", "nvidia/segformer-b3-finetuned-ade-512-512")
    USE_REAL_MODELS: bool = True
    MAX_CONCURRENCY: int = 4

    # OSM Overpass API URL
    OVERPASS_API_URL: str = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")

    PUBLIC_API_URL: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
