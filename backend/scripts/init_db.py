import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import hash_password
from app.core.constants import MATERIAL_TYPES
from datetime import datetime
import logging

# Import all models so their tables are registered with Base
import app.models.product  # noqa: F401
import app.models.client  # noqa: F401
import app.models.employee  # noqa: F401
import app.models.payment  # noqa: F401
import app.models.attendance  # noqa: F401
import app.models.client_project  # noqa: F401
import app.models.estimate  # noqa: F401
import app.models.candidate  # noqa: F401
import app.models.interview  # noqa: F401
import app.models.salary_slip  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def seed_master_users():
    """Seed initial master users from environment variables."""
    db = SessionLocal()
    try:
        master_email = os.getenv("MASTER_USER_EMAIL", "admin@woodfulcreations.com")
        master_username = os.getenv("MASTER_USER_USERNAME", "admin")
        master_full_name = os.getenv("MASTER_USER_FULL_NAME", "Administrator")
        master_password = os.getenv("MASTER_USER_PASSWORD")

        if not master_password:
            logger.warning(
                "MASTER_USER_PASSWORD environment variable not set. Skipping master user seed."
            )
            return

        existing = db.query(User).filter(User.email == master_email).first()
        if not existing:
            user = User(
                email=master_email,
                username=master_username,
                full_name=master_full_name,
                password_hash=hash_password(master_password),
                is_active=True,
                role="master"
            )
            db.add(user)
            db.commit()
            logger.info("Master user created: %s", master_username)
        else:
            logger.info("Master user already exists: %s", master_email)
    except Exception as e:
        logger.error("Error seeding users: %s", str(e))
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Initializing Woodful Creations database...")
    init_database()
    seed_master_users()
    logger.info("Database initialization complete")