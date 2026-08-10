"""
Create all tables directly from the current SQLAlchemy models.

For local SQLite development this is a convenient shortcut. For anything
beyond local dev (staging/production, or any Postgres deployment), use
Alembic migrations instead (see backend/alembic/) so schema changes are
tracked and reversible - this script does not know how to migrate an
existing database, only create tables that don't exist yet.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine
from app import models  # noqa: F401 - registers every model on Base.metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


if __name__ == "__main__":
    init_database()
    logger.info(
        "Done. Create your first admin user with: "
        "python scripts/create_master_user.py --email you@example.com --username you --name \"Your Name\""
    )
