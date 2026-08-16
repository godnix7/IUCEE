import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Create all tables and seed default admin/planner users if DB is empty."""
    from app.models import User, Project
    from app.core.security import hash_password

    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.email == "admin@urbansense.ai").first()
        if not admin_user:
            admin_user = User(
                email="admin@urbansense.ai",
                hashed_password=hash_password("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True
            )
            db.add(admin_user)

        planner_user = db.query(User).filter(User.email == "planner@urbansense.ai").first()
        if not planner_user:
            planner_user = User(
                email="planner@urbansense.ai",
                hashed_password=hash_password("planner123"),
                full_name="Urban Planner",
                role="planner",
                is_active=True
            )
            db.add(planner_user)

        viewer_user = db.query(User).filter(User.email == "viewer@urbansense.ai").first()
        if not viewer_user:
            viewer_user = User(
                email="viewer@urbansense.ai",
                hashed_password=hash_password("viewer123"),
                full_name="Public Viewer",
                role="viewer",
                is_active=True
            )
            db.add(viewer_user)

        db.commit()

        # Seed initial default project if none exists
        if db.query(Project).count() == 0:
            default_proj = Project(
                name="Metropolitan Infrastructure Survey 2026",
                description="Default GIS imagery analysis project for urban density and infrastructure benchmarking.",
                created_by_id=admin_user.id
            )
            db.add(default_proj)
            db.commit()
    finally:
        db.close()
