"""Database configuration and session management"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLite needs special handling
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    # Never echo SQL in production regardless of DEBUG flag
    "echo": settings.DEBUG and settings.ENVIRONMENT != "production",
}

if _is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

# Create database engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Enable WAL mode and foreign keys for SQLite
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
