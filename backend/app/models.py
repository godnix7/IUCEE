from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="planner", index=True) # 'admin', 'planner', 'viewer'
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    projects = relationship("Project", back_populates="created_by_user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True) # e.g. 'LOGIN', 'UPLOAD_IMAGERY', 'RUN_INFERENCE'
    ip_address = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    created_by_user = relationship("User", back_populates="projects")
    analyses = relationship("ImageryAnalysis", back_populates="project", cascade="all, delete-orphan")

class ImageryAnalysis(Base):
    __tablename__ = "imagery_analyses"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, default="geotiff") # 'geotiff', 'drone_ortho', 'satellite_png'
    crs = Column(String, default="EPSG:4326")
    bounds = Column(JSON, nullable=True) # [min_lon, min_lat, max_lon, max_lat]
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    population_estimate = Column(Integer, default=1000)
    
    # 'pending', 'processing', 'completed', 'failed'
    status = Column(String, default="pending", index=True)
    inference_time_sec = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="analyses")
    spatial_features = relationship("SpatialFeature", back_populates="analysis", cascade="all, delete-orphan")
    benchmark = relationship("UrbanBenchmark", back_populates="analysis", uselist=False, cascade="all, delete-orphan")

class SpatialFeature(Base):
    __tablename__ = "spatial_features"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), index=True)
    
    # AI Detects: 'road', 'building', 'tree_cover', 'water', 'barren_land', 'built_up'
    # OSM Enricher: 'hospital', 'school', 'police_station', 'fire_station', 'slum'
    class_name = Column(String, index=True, nullable=False)
    source = Column(String, default="ai_segformer") # 'ai_segformer', 'osm_layer'
    confidence = Column(Float, default=1.0)
    area_sq_meters = Column(Float, default=0.0)
    feature_count = Column(Integer, default=1)
    
    geometry_json = Column(JSON, nullable=False)
    properties = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", back_populates="spatial_features")

class UrbanBenchmark(Base):
    __tablename__ = "urban_benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), unique=True, index=True)
    
    population_count = Column(Integer, default=1000)
    road_density_km_per_sqkm = Column(Float, default=0.0)
    building_coverage_pct = Column(Float, default=0.0)
    tree_cover_pct = Column(Float, default=0.0)
    water_cover_pct = Column(Float, default=0.0)
    built_up_ratio = Column(Float, default=0.0)
    hospitals_per_10k_pop = Column(Float, default=0.0)
    schools_per_10k_pop = Column(Float, default=0.0)
    infrastructure_score = Column(Float, default=0.0) # 0.0 to 100.0 score

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", back_populates="benchmark")
