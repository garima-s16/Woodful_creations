"""
Database Configuration and Session Management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_engine_kwargs = {"echo": settings.DEBUG, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    # SQLite's default pool implementation doesn't accept pool_size/max_overflow.
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
