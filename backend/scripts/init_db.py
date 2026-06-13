import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal, User, StockItem
from app.core.security import hash_password
from app.core.constants import MATERIAL_TYPES
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def seed_master_users():
    db = SessionLocal()
    try:
        existing_nikhil = db.query(User).filter(User.email == "nikhils@woodful.com").first()
        existing_garima = db.query(User).filter(User.email == "garimas@woodful.com").first()
        
        if not existing_nikhil:
            nikhil = User(
                email="nikhils@woodful.com",
                username="nikhils",
                full_name="Nikhil",
                hashed_password=hash_password("Nikhil*27"),
                is_active=True,
                is_master=True,
                role="master"
            )
            db.add(nikhil)
            logger.info("Master user Nikhil created")
        
        if not existing_garima:
            garima = User(
                email="garimas@woodful.com",
                username="garimas",
                full_name="Garima",
                hashed_password=hash_password("Gullak*16"),
                is_active=True,
                is_master=True,
                role="master"
            )
            db.add(garima)
            logger.info("Master user Garima created")
        
        db.commit()
    except Exception as e:
        logger.error(f"Error seeding users: {str(e)}")
        db.rollback()
    finally:
        db.close()

def seed_materials():
    db = SessionLocal()
    try:
        existing_count = db.query(StockItem).count()
        if existing_count > 0:
            logger.info(f"Materials already exist ({existing_count}). Skipping seed.")
            return
        
        counter = 0
        for material_name, thicknesses in MATERIAL_TYPES.items():
            for thickness in thicknesses:
                item = StockItem(
                    sku=f"{material_name.replace(' ', '_').upper()}_{thickness}MM",
                    name=material_name,
                    category=material_name,
                    description=f"{material_name} - {thickness}mm thickness",
                    quantity=0,
                    min_stock=10,
                    reorder_qty=50,
                    unit_cost=100.0,
                    selling_price=150.0,
                    is_active=True,
                    created_by=1
                )
                db.add(item)
                counter += 1
        
        db.commit()
        logger.info(f"Seeded {counter} material items")
    except Exception as e:
        logger.error(f"Error seeding materials: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing Woodful Creations database...")
    init_database()
    seed_master_users()
    seed_materials()
    logger.info("Database initialization complete")