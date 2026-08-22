from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean, JSON, BigInteger
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
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
    # Analysis pipeline: 'segmentation' (LoveDA land-cover) or 'detection' (COCO object detection)
    analysis_mode = Column(String, default="segmentation", index=True)
    # Spatial metadata
    original_crs = Column(String, nullable=True)
    normalized_crs = Column(String, default="EPSG:4326")
    bounds = Column(JSON, nullable=True) # [min_x, min_y, max_x, max_y] (geographic)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    resolution_x = Column(Float, nullable=True)
    resolution_y = Column(Float, nullable=True)
    footprint = Column(Geometry("POLYGON", srid=4326, spatial_index=True), nullable=True)

    population_count = Column(Integer, nullable=True)
    population_source = Column(String, nullable=True)
    population_date = Column(DateTime, nullable=True)
    
    # 'pending', 'processing', 'completed', 'failed'
    status = Column(String, default="pending", index=True)
    osm_enrichment_status = Column(String, default="pending", index=True)
    inference_time_sec = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    # Detection-mode outputs (object detection on drone/oblique imagery)
    detection_overlay_key = Column(String, nullable=True)  # MinIO key of annotated image
    detection_summary = Column(JSON, nullable=True)        # {class: count, ...} + totals
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="analyses")
    spatial_features = relationship("SpatialFeature", back_populates="analysis", cascade="all, delete-orphan")
    osm_features = relationship("OSMFeature", back_populates="analysis", cascade="all, delete-orphan")
    analytics = relationship("SpatialAnalytics", back_populates="analysis", uselist=False, cascade="all, delete-orphan")

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
    
    # Metadata
    model_name = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    source_identifier = Column(String, nullable=True)
    
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=True)
    properties = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", back_populates="spatial_features")
    
class OSMFeature(Base):
    __tablename__ = "osm_features"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), index=True)
    
    osm_type = Column(String, index=True, nullable=False) # 'node', 'way', 'relation'
    osm_id = Column(BigInteger, index=True, nullable=False)
    
    category = Column(String, index=True, nullable=False) # 'hospital', 'school', 'police', 'fire_station'
    name = Column(String, nullable=True)
    source = Column(String, default="openstreetmap")
    
    geometry = Column(Geometry("GEOMETRY", srid=4326, spatial_index=True), nullable=True)
    tags = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", back_populates="osm_features")

class SpatialAnalytics(Base):
    __tablename__ = "spatial_analytics"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), unique=True, index=True)
    
    population_count = Column(Integer, nullable=True)
    population_source = Column(String, nullable=True)
    population_date = Column(DateTime, nullable=True)
    
    analysis_area_sq_km = Column(Float, nullable=True)

    road_area_sq_m = Column(Float, nullable=True)
    road_coverage_pct = Column(Float, nullable=True)
    
    building_area_sq_m = Column(Float, nullable=True)
    building_coverage_pct = Column(Float, nullable=True)

    tree_area_sq_m = Column(Float, nullable=True)
    tree_cover_pct = Column(Float, nullable=True)
    water_area_sq_m = Column(Float, nullable=True)
    water_cover_pct = Column(Float, nullable=True)
    
    barren_area_sq_m = Column(Float, nullable=True)
    barren_cover_pct = Column(Float, nullable=True)
    agriculture_area_sq_m = Column(Float, nullable=True)
    agriculture_cover_pct = Column(Float, nullable=True)

    hospital_count = Column(Integer, nullable=True)
    school_count = Column(Integer, nullable=True)
    police_count = Column(Integer, nullable=True)
    fire_station_count = Column(Integer, nullable=True)

    hospitals_per_1000 = Column(Float, nullable=True)
    schools_per_1000 = Column(Float, nullable=True)

    infrastructure_score = Column(Float, nullable=True)
    component_scores = Column(JSON, nullable=True)
    formula_version = Column(String, default="1.0")
    
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", back_populates="analytics")

class BenchmarkDefinition(Base):
    __tablename__ = "benchmark_definitions"

    id = Column(Integer, primary_key=True, index=True)
    indicator = Column(String, unique=True, index=True, nullable=False)
    unit = Column(String, nullable=False)
    target_value = Column(Float, nullable=False)
    source = Column(String, nullable=False)
    reference_name = Column(String, nullable=False)
    effective_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

class RefreshToken(Base):
    """Persistent refresh token for secure rotation and family-level reuse detection."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    token_family_id = Column(String, nullable=False, index=True)  # UUID grouping tokens in a rotation chain
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)  # Set when token is revoked
    replaced_by_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    user = relationship("User")
    replaced_by = relationship("RefreshToken", remote_side=[id])


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), index=True, nullable=False)
    job_type = Column(String, default="analysis", index=True)
    status = Column(String, default="queued", index=True) # queued, running, retrying, completed, failed, cancelled
    progress = Column(Integer, default=0)
    current_stage = Column(String, nullable=True) # VALIDATING, PREPARING_RASTER, AI_INFERENCE, POSTGIS_PERSISTENCE, OSM_ENRICHMENT, FINALIZING
    message = Column(Text, nullable=True)
    attempt = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)
    
    worker_id = Column(String, nullable=True)
    celery_task_id = Column(String, nullable=True, index=True)
    
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis", backref="jobs")


class DetectionReview(Base):
    """
    Human QA / relabeling record for an AI-detected SpatialFeature.

    Provenance-preserving: the original AI prediction is NEVER overwritten. This row records
    the original label at review time plus any human correction, keeping full auditability.
    One current review per feature (upserted); the review row itself preserves original vs
    corrected so the AI's prediction always remains available.
    """
    __tablename__ = "detection_reviews"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), index=True, nullable=False)
    feature_id = Column(Integer, ForeignKey("spatial_features.id", ondelete="CASCADE"), index=True, nullable=False, unique=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Provenance (original AI prediction — never mutated)
    original_label = Column(String, nullable=False)
    original_source = Column(String, nullable=True)   # e.g. ai_segformer_loveda / detection_yolos

    # Human correction (only set when relabeling)
    corrected_label = Column(String, nullable=True)
    review_source = Column(String, default="human_review")

    # pending | accepted | needs_relabel | rejected
    status = Column(String, default="pending", index=True)
    comment = Column(Text, nullable=True)

    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis")
    feature = relationship("SpatialFeature")
    reviewer = relationship("User")


class AnalysisReview(Base):
    """
    Image-level (whole-analysis) human verdict. One review per analysis (upserted).

    Instead of per-class decisions, the reviewer accepts the whole image, or flags it
    ('needs_relabel') which re-sends the entire image through the pipeline for reprocessing,
    or rejects it. The AI output is never mutated — this is a QA verdict + audit record.
    """
    __tablename__ = "analysis_reviews"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("imagery_analyses.id"), index=True, nullable=False, unique=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # accepted | needs_relabel | rejected | pending
    status = Column(String, default="pending", index=True)
    comment = Column(Text, nullable=True)
    review_source = Column(String, default="human_review")

    # Re-send provenance: set when a 'needs_relabel' verdict re-queues the whole image
    resent = Column(Boolean, default=False)
    resent_job_id = Column(Integer, nullable=True)

    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    analysis = relationship("ImageryAnalysis")
    reviewer = relationship("User")
