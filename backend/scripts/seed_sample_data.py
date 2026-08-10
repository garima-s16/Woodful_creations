"""
Seed development data: material catalog (from MATERIAL_TYPES) and a couple
of sample clients. Safe to re-run - skips rows that already exist.

This does NOT create any users - run create_master_user.py for that so
credentials are never hardcoded in source.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.constants import MATERIAL_TYPES
from app.core.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models.client import Client
from app.models.product import Product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_products():
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            logger.info("Products already exist - skipping product seed.")
            return

        count = 0
        for material_name, thicknesses in MATERIAL_TYPES.items():
            for thickness in thicknesses:
                sku = f"{material_name.replace(' ', '_').upper()}_{thickness}MM"
                db.add(Product(
                    material_type=material_name,
                    thickness=thickness,
                    category=material_name,
                    description=f"{material_name} - {thickness}mm thickness",
                    quantity=0,
                    min_quantity=10,
                    price_per_unit=0,
                    unit="sheets",
                    sku=sku,
                ))
                count += 1
        db.commit()
        logger.info("Seeded %d product SKUs.", count)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_clients():
    db = SessionLocal()
    try:
        if db.query(Client).count() > 0:
            logger.info("Clients already exist - skipping client seed.")
            return

        sample_clients = [
            {"client_id": "CLI-0001", "name": "Sample Client One", "city": "Delhi", "lead_source": "Referral"},
            {"client_id": "CLI-0002", "name": "Sample Client Two", "city": "Mumbai", "lead_source": "Website"},
        ]
        for c in sample_clients:
            db.add(Client(**c))
        db.commit()
        logger.info("Seeded %d sample clients.", len(sample_clients))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_products()
    seed_clients()
    logger.info("Seed complete.")
