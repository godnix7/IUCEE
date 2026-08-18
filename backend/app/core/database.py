import os
from sqlalchemy import text
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
    """Create all tables. Seed default users ONLY in development mode."""
    from app.models import User, Project, RefreshToken
    from app.core.security import hash_password

    Base.metadata.create_all(bind=engine)

    if settings.ENVIRONMENT != "development":
        _validate_postgis_available()
        return
    
    db = SessionLocal()
    try:
        _seed_user(db, settings.SEED_ADMIN_EMAIL, settings.SEED_ADMIN_PASSWORD, "System Administrator", "admin")
        _seed_user(db, settings.SEED_PLANNER_EMAIL, settings.SEED_PLANNER_PASSWORD, "Urban Planner", "planner")
        _seed_user(db, settings.SEED_VIEWER_EMAIL, settings.SEED_VIEWER_PASSWORD, "Public Viewer", "viewer")
        db.commit()

        # Seed initial default project if none exists
        from app.models import Project
        admin_user = db.query(User).filter(User.email == settings.SEED_ADMIN_EMAIL).first()
        if admin_user and db.query(Project).count() == 0:
            default_proj = Project(
                name="Metropolitan Infrastructure Survey 2026",
                description="Default GIS imagery analysis project for urban density and infrastructure benchmarking.",
                created_by_id=admin_user.id
            )
            db.add(default_proj)
            db.commit()
            print("[DEV SEED] Created default project")

        _seed_benchmarks(db)
        db.commit()
    finally:
        db.close()


def _validate_postgis_available() -> None:
    """Fail fast if the configured database is not a working PostGIS instance."""
    if settings.DATABASE_URL.startswith("sqlite"):
        raise ValueError("UrbanSense production requires PostgreSQL + PostGIS, not SQLite.")

    db = SessionLocal()
    try:
        db.execute(text("SELECT PostGIS_Full_Version()"))
    except Exception as exc:
        raise ValueError(
            "UrbanSense production requires a working PostGIS database with the PostGIS extension installed."
        ) from exc
    finally:
        db.close()


def _seed_user(db, email: str, password: str, full_name: str, role: str):
    """Create a seed user if the email/password env vars are provided and user doesn't exist."""
    from app.models import User
    from app.core.security import hash_password

    if not email or not password:
        print(f"[DEV SEED] Skipping {role} user — SEED_{role.upper()}_EMAIL or SEED_{role.upper()}_PASSWORD not set")
        return

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True
    )
    db.add(user)
    print(f"[DEV SEED] Created {role} user: {email}")

def _seed_benchmarks(db):
    """Seed default benchmark definitions for development mode if none exist."""
    from app.models import BenchmarkDefinition
    if db.query(BenchmarkDefinition).count() > 0:
        return

    defaults = [
        {"indicator": "tree_cover_pct", "unit": "%", "target_value": 15.0, "source": "UrbanSense Development Configuration", "reference_name": "Development Configuration", "notes": "Minimum tree cover recommended for urban centers."},
        {"indicator": "road_coverage_pct", "unit": "%", "target_value": 5.0, "source": "UrbanSense Development Configuration", "reference_name": "Development Configuration", "notes": "Minimum optimal road coverage network."},
        {"indicator": "hospitals_per_1000", "unit": "per 1,000", "target_value": 0.5, "source": "UrbanSense Development Configuration", "reference_name": "Development Configuration", "notes": "Hospitals per 1,000 residents."},
        {"indicator": "schools_per_1000", "unit": "per 1,000", "target_value": 1.0, "source": "UrbanSense Development Configuration", "reference_name": "Development Configuration", "notes": "Schools per 1,000 residents."}
    ]

    for b in defaults:
        db.add(BenchmarkDefinition(**b))
    
    print("[DEV SEED] Created default benchmarks")

