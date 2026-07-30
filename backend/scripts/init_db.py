"""
Database initialization and seeding script.
Run once after setting up PostgreSQL to create tables and seed initial data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.product import Product
from app.core.security import hash_password
from app.core.constants import MATERIAL_TYPES
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def seed_master_users():
    """
    Seeds master administrator accounts.
    Passwords are read from environment variables MASTER_USER1_PASSWORD and
    MASTER_USER2_PASSWORD to avoid storing credentials in source code.
    Set these variables before running this script.
    """
    password1 = os.getenv("MASTER_USER1_PASSWORD")
    password2 = os.getenv("MASTER_USER2_PASSWORD")

    if not password1 or not password2:
        logger.error(
            "MASTER_USER1_PASSWORD and MASTER_USER2_PASSWORD environment variables must be set. "
            "Example: export MASTER_USER1_PASSWORD='<strong-password>'"
        )
        return

    db = SessionLocal()
    try:
        existing1 = db.query(User).filter(User.email == "nikhils@woodful.com").first()
        existing2 = db.query(User).filter(User.email == "garimas@woodful.com").first()

        if not existing1:
            user1 = User(
                email="nikhils@woodful.com",
                username="nikhils",
                full_name="Nikhil",
                password_hash=hash_password(password1),
                is_active=True,
                role="master"
            )
            db.add(user1)
            logger.info("Master user nikhils created")

        if not existing2:
            user2 = User(
                email="garimas@woodful.com",
                username="garimas",
                full_name="Garima",
                password_hash=hash_password(password2),
                is_active=True,
                role="master"
            )
            db.add(user2)
            logger.info("Master user garimas created")

        db.commit()
    except Exception as e:
        logger.error(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()


def seed_materials():
    """Seeds the product catalogue with standard material types and thicknesses."""
    db = SessionLocal()
    try:
        existing_count = db.query(Product).count()
        if existing_count > 0:
            logger.info(f"Products already exist ({existing_count}). Skipping seed.")
            return

        counter = 0
        for material_name, thicknesses in MATERIAL_TYPES.items():
            for thickness in thicknesses:
                sku = f"{material_name.replace(' ', '_').replace('/', '_').upper()}_{thickness}MM"
                item = Product(
                    material_type=material_name,
                    thickness=thickness,
                    category=material_name,
                    description=f"{material_name} - {thickness}mm thickness",
                    quantity=0,
                    min_quantity=10,
                    price_per_unit=0.0,
                    unit="sheets",
                    sku=sku,
                )
                db.add(item)
                counter += 1

        db.commit()
        logger.info(f"Seeded {counter} material items")
    except Exception as e:
        logger.error(f"Error seeding materials: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Initializing Woodful Creations database...")
    init_database()
    seed_master_users()
    seed_materials()
    logger.info("Database initialization complete")
