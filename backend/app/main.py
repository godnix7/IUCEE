from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.api import projects, labeling, review, dashboard, exports
from app.services.processing_service import ProcessingService

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "exports"), exist_ok=True)

# Static file serving (for thumbnails and images)
# In production, use nginx for this.
app.mount("/static", StaticFiles(directory=settings.DATA_DIR), name="static")

# Include routers
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(labeling.router, prefix=f"{settings.API_V1_STR}/labeling", tags=["labeling"])
app.include_router(review.router, prefix=f"{settings.API_V1_STR}/review", tags=["review"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["dashboard"])
app.include_router(exports.router, prefix=f"{settings.API_V1_STR}/exports", tags=["exports"])

@app.on_event("startup")
def startup_event():
    from app.services.hardware_service import HardwareService
    HardwareService.print_startup_check()
    
    # Worker is purposefully NOT started on boot. 
    # It will only start when the user clicks 'Start' in the Dashboard.

@app.get("/")
def root():
    return {"message": "Welcome to AI Pixel Annotation Studio API"}
