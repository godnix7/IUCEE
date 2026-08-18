import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "UrbanSense - AI Powered Urban Infrastructure Intelligence System"
    API_V1_STR: str = "/api/v1"
    
    # Environment: 'development' or 'production'
    # Controls seed user creation and secret validation
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database URL: PostGIS in production, SQLite allowed in development
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'urbansense.db')}"
    )

    # JWT Security — NO insecure fallback in production
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Storage settings
    DATA_DIR: str = os.getenv(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    )

    # File upload validation
    SUPPORTED_EXTENSIONS: List[str] = [".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"]
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

    # AI Model settings
    PRETRAINED_SEGFORMER_MODEL: str = os.getenv(
        "PRETRAINED_SEGFORMER_MODEL",
        "wu-pr-gw/segformer-b2-finetuned-with-LoveDA"
    )
    USE_REAL_MODELS: bool = True
    MAX_CONCURRENCY: int = int(os.getenv("MAX_CONCURRENCY", "4"))

    # OSM Overpass API configuration
    OVERPASS_URL: str = os.getenv("OVERPASS_URL", "https://overpass.osm.ch/api/interpreter")
    OSM_REQUEST_TIMEOUT: int = int(os.getenv("OSM_REQUEST_TIMEOUT", "30"))
    OSM_MAX_RETRIES: int = int(os.getenv("OSM_MAX_RETRIES", "2"))
    OSM_ENABLED: bool = os.getenv("OSM_ENABLED", "true").lower() == "true"
    PUBLIC_API_URL: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

    # Celery & Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_WORKER_CONCURRENCY: int = int(os.getenv("CELERY_WORKER_CONCURRENCY", "2"))
    MAX_TASK_RETRIES: int = int(os.getenv("MAX_TASK_RETRIES", "3"))

    # MinIO / S3 Storage Configuration
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "urbansense-uploads")

    # Development seed credentials (only used when ENVIRONMENT=development)
    SEED_ADMIN_EMAIL: str = os.getenv("SEED_ADMIN_EMAIL", "admin@urbansense.ai")
    SEED_ADMIN_PASSWORD: str = os.getenv("SEED_ADMIN_PASSWORD", "")
    SEED_PLANNER_EMAIL: str = os.getenv("SEED_PLANNER_EMAIL", "planner@urbansense.ai")
    SEED_PLANNER_PASSWORD: str = os.getenv("SEED_PLANNER_PASSWORD", "")
    SEED_VIEWER_EMAIL: str = os.getenv("SEED_VIEWER_EMAIL", "viewer@urbansense.ai")
    SEED_VIEWER_PASSWORD: str = os.getenv("SEED_VIEWER_PASSWORD", "")

    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def validate_production_config(s: Settings) -> None:
    """Raise ValueError if mandatory production secrets are missing."""
    if s.ENVIRONMENT != "development":
        errors = []
        if not s.SECRET_KEY:
            errors.append("SECRET_KEY is required in production. Set it via environment variable.")
        try:
            parsed_url = make_url(s.DATABASE_URL)
        except Exception:
            parsed_url = None
        if not parsed_url or parsed_url.drivername.startswith("sqlite"):
            errors.append("SQLite is not supported in production. Set DATABASE_URL to a PostgreSQL/PostGIS connection string.")
        elif not parsed_url.username or not parsed_url.password:
            errors.append("DATABASE_URL must include both a database username and password in production.")
        if not s.MINIO_ACCESS_KEY:
            errors.append("MINIO_ROOT_USER is required in production. Set it via environment variable.")
        if not s.MINIO_SECRET_KEY:
            errors.append("MINIO_ROOT_PASSWORD is required in production. Set it via environment variable.")
        if errors:
            raise ValueError(
                f"UrbanSense production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )
    else:
        # In development, use a deterministic fallback secret if none provided
        if not s.SECRET_KEY:
            s.SECRET_KEY = "urbansense_dev_only_secret_not_for_production"


settings = Settings()
validate_production_config(settings)
