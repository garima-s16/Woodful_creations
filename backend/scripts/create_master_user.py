import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_master_user(email: str, username: str, full_name: str, password: str):
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            logger.error("User with email or username already exists")
            return False

        user = User(
            email=email,
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            is_active=True,
            role="master"
        )

        db.add(user)
        db.commit()
        logger.info("Master user %s created successfully", username)
        return True
    except Exception as e:
        logger.error("Error creating user: %s", str(e))
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a master user")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--password", required=True, help="Password")

    args = parser.parse_args()
    create_master_user(args.email, args.username, args.name, args.password)
