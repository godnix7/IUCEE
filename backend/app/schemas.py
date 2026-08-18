from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth & User Schemas ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")
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
    """Login response — access_token in body, refresh_token set as HttpOnly cookie."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefreshResponse(BaseModel):
    """Refresh response — new access_token in body, new refresh cookie set."""
    access_token: str
    token_type: str = "bearer"

class TokenRefreshRequest(BaseModel):
    """Fallback for non-cookie refresh (e.g. mobile clients)."""
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

# --- Benchmark & Analytics Schemas ---
class BenchmarkDefinitionResponse(BaseModel):
    id: int
    indicator: str
    unit: str
    target_value: float
    source: str
    reference_name: str
    
    class Config:
        from_attributes = True

class BenchmarkCreate(BaseModel):
    indicator: str
    unit: str
    target_value: float
    source: str
    reference_name: str
    notes: Optional[str] = None

class BenchmarkUpdate(BaseModel):
    indicator: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    source: Optional[str] = None
    reference_name: Optional[str] = None
    notes: Optional[str] = None

class PopulationSchema(BaseModel):
    count: Optional[int] = None
    source: Optional[str] = None
    date: Optional[datetime] = None

class InfrastructureSchema(BaseModel):
    road_area_sq_m: Optional[float] = None
    road_coverage_pct: Optional[float] = None
    building_coverage_pct: Optional[float] = None
    tree_cover_pct: Optional[float] = None
    water_cover_pct: Optional[float] = None
    agriculture_cover_pct: Optional[float] = None
    barren_cover_pct: Optional[float] = None

class FacilitiesSchema(BaseModel):
    hospitals: Optional[int] = None
    schools: Optional[int] = None
    police: Optional[int] = None
    fire_stations: Optional[int] = None

class NormalizedSchema(BaseModel):
    hospitals_per_1000: Optional[float] = None
    schools_per_1000: Optional[float] = None

class AnalyticsResponse(BaseModel):
    analysis_id: int
    status: Optional[str] = None
    area_sq_km: Optional[float] = None
    population: Optional[PopulationSchema] = None
    infrastructure: Optional[InfrastructureSchema] = None
    facilities: Optional[FacilitiesSchema] = None
    normalized: Optional[NormalizedSchema] = None
    score: Optional[float] = None
    component_scores: Optional[Dict[str, Any]] = None
    formula_version: Optional[str] = None
    calculated_at: Optional[datetime] = None

# --- Imagery Analysis Schemas ---
class AnalysisCreate(BaseModel):
    project_id: int
    population_count: Optional[int] = None
    population_source: Optional[str] = None

class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_path: str
    file_type: str
    original_crs: Optional[str] = None
    normalized_crs: Optional[str] = None
    bounds: Optional[List[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    resolution_x: Optional[float] = None
    resolution_y: Optional[float] = None
    population_count: Optional[int] = None
    population_source: Optional[str] = None
    population_date: Optional[datetime] = None
    status: str
    inference_time_sec: Optional[float] = None
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime


    class Config:
        from_attributes = True

# --- Dashboard & Analytics Schemas ---
class DashboardStatsResponse(BaseModel):
    total_analyses: int
    recent_analyses: List[AnalysisResponse]
    processing_queue_count: int
    active_users_count: int
