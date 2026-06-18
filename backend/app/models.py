from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    root_path = Column(String)
    ls_project_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    classes = relationship("ProjectClass", back_populates="project", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="project", cascade="all, delete-orphan")

class ProjectClass(Base):
    __tablename__ = "project_classes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String, index=True)
    color = Column(String)
    shortcut_key = Column(String, nullable=True)

    project = relationship("Project", back_populates="classes")

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    filename = Column(String, index=True)
    relative_path = Column(String)
    absolute_path = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    file_size_bytes = Column(Integer)
    ls_task_id = Column(Integer, nullable=True, index=True)
    
    # pending, processing, completed, failed
    status = Column(String, default="pending", index=True) 
    
    # accepted, rejected, manual_review
    review_status = Column(String, default="accepted", index=True)
    
    confidence = Column(Float, nullable=True)
    agreement_score = Column(Float, nullable=True)
    
    mask_path = Column(String, nullable=True)
    confidence_map_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    file_hash = Column(String, nullable=True, index=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    is_corrupt = Column(Boolean, default=False)
    
    rejection_reason = Column(String, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_viewed = Column(DateTime, nullable=True)
    reviewer = Column(String, nullable=True)
    correction_count = Column(Integer, default=0)

    project = relationship("Project", back_populates="images")
    annotations = relationship("Annotation", back_populates="image", cascade="all, delete-orphan")
    processing_queue = relationship("ProcessingQueue", back_populates="image", uselist=False, cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="image", cascade="all, delete-orphan")
    tiles = relationship("ImageTile", back_populates="image", cascade="all, delete-orphan")

class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"))
    class_name = Column(String, index=True)
    model_source = Column(String)
    confidence = Column(Float, nullable=True)
    
    segmentation_json = Column(Text, nullable=True)
    bbox_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    image = relationship("Image", back_populates="annotations")

class ProcessingQueue(Base):
    __tablename__ = "processing_queue"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), unique=True)
    
    # pending, processing, completed, failed
    status = Column(String, default="pending", index=True)
    
    model_name = Column(String, default="nvidia/segformer-b3-finetuned-ade-512-512")
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)

    image = relationship("Image", back_populates="processing_queue")

class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"))
    
    # rejected, corrected
    action = Column(String)
    reason = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Used for feedback loop learning (confusion matrix tracking)
    predicted_class = Column(String, nullable=True)
    actual_class = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    image = relationship("Image", back_populates="review_logs")

class PredictionVsCorrection(Base):
    __tablename__ = "prediction_vs_correction"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"))
    
    original_prediction_json = Column(Text)
    human_correction_json = Column(Text)
    correction_type = Column(String) # e.g., "class_change", "mask_edit", "polygon_edit", "new_region"
    
    region_id = Column(String, nullable=True)
    predicted_class = Column(String, nullable=True)
    corrected_class = Column(String, nullable=True)
    
    confidence = Column(Float, nullable=True)
    reviewer = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    image = relationship("Image")


class ImageTile(Base):
    __tablename__ = "image_tiles"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), index=True)
    tile_index = Column(Integer)
    x = Column(Integer)
    y = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    metadata_json = Column(Text, nullable=True)

    image = relationship("Image", back_populates="tiles")
