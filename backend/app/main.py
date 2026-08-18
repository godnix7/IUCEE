import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import auth, projects, inference, gis, analytics, reports, users, jobs, benchmarks

# Initialize database schema and seed users (development only)
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS middleware — credentials=True requires specific origins (no wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global exception handler — structured errors, no Python stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred.",
            "details": {} if settings.ENVIRONMENT != "development" else {"exception": str(exc)},
        },
    )

# Ensure data directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.DATA_DIR), name="static")

# Register API V1 Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(inference.router, prefix=f"{settings.API_V1_STR}/inference", tags=["inference"])
app.include_router(gis.router, prefix=f"{settings.API_V1_STR}/gis", tags=["gis"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(reports.router, prefix=f"{settings.API_V1_STR}/reports", tags=["reports"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(benchmarks.router, prefix="/api/v1/benchmarks", tags=["Benchmarks"])

@app.get("/health")
def health_check():
    import redis
    from app.core.database import SessionLocal
    from app.services.storage_service import StorageService
    from sqlalchemy import text
    
    health_status = {
        "api": "ok",
        "database": "ok",
        "redis": "ok",
        "storage": "ok"
    }
    
    # Check Database
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        health_status["database"] = "down"
    finally:
        db.close()
        
    # Check Redis
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
    except Exception:
        health_status["redis"] = "down"
        
    # Check Storage
    try:
        s3 = StorageService.get_client()
        s3.list_buckets()
    except Exception:
        health_status["storage"] = "down"
        
    is_healthy = all(v == "ok" for v in health_status.values())
    status_code = 200 if is_healthy else 503
    return JSONResponse(status_code=status_code, content=health_status)

@app.get("/")
def root():
    return {
        "system": "UrbanSense AI Powered Urban Infrastructure Intelligence System API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
