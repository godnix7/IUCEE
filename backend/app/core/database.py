from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from .config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

def check_and_migrate_db(engine, Base):
    """
    Checks if there are any columns defined in the SQLAlchemy models that are missing
    from the actual database tables. If so, adds them dynamically via ALTER TABLE.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if inspector.has_table(table_name):
                existing_cols = {col['name'] for col in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name not in existing_cols:
                        col_type = column.type.compile(dialect=engine.dialect)
                        null_str = "" if column.nullable else " NOT NULL"
                        default_str = ""
                        if column.default is not None and not callable(column.default.arg):
                            default_str = f" DEFAULT {column.default.arg}"
                        
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{null_str}{default_str}"
                        print(f"Migrating database: Running '{alter_query}'")
                        conn.execute(text(alter_query))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

