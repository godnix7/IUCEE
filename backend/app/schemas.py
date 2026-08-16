from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth & User Schemas ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Optional[str] = "planner"

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefreshRequest(BaseModel):
    refresh_token: str

# --- Project Schemas ---
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by_id: Optional[int]
    created_at: datetime
    analysis_count: Optional[int] = 0

    class Config:
        from_attributes = True

# --- Spatial Feature Schemas ---
class SpatialFeatureResponse(BaseModel):
    id: int
    analysis_id: int
    class_name: str
    source: str
    confidence: float
    area_sq_meters: float
    feature_count: int
    geometry_json: Dict[str, Any]
    properties: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# --- Urban Benchmark Schemas ---
class UrbanBenchmarkResponse(BaseModel):
    id: int
    analysis_id: int
    population_count: int
    road_density_km_per_sqkm: float
    building_coverage_pct: float
    tree_cover_pct: float
    water_cover_pct: float
    built_up_ratio: float
    hospitals_per_10k_pop: float
    schools_per_10k_pop: float
    infrastructure_score: float
    created_at: datetime

    class Config:
        from_attributes = True

# --- Imagery Analysis Schemas ---
class AnalysisCreate(BaseModel):
    project_id: int
    population_estimate: Optional[int] = 1000

class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_path: str
    file_type: str
    crs: str
    bounds: Optional[List[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    population_estimate: int
    status: str
    inference_time_sec: Optional[float] = None
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    benchmark: Optional[UrbanBenchmarkResponse] = None

    class Config:
        from_attributes = True

# --- Dashboard & Analytics Schemas ---
class DashboardStatsResponse(BaseModel):
    total_analyses: int
    infrastructure_coverage_pct: float
    roads_detected_km: float
    buildings_detected_count: int
    water_bodies_count: int
    tree_coverage_pct: float
    population_mapped: int
    infrastructure_score: float
    benchmark_status: str
    recent_analyses: List[AnalysisResponse]
    processing_queue_count: int
    active_users_count: int
