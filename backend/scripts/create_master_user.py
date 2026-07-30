"""
Script to create a master administrator user.
Usage: python create_master_user.py --email <email> --username <username> --name <name>
The password is read interactively or from the MASTER_PASSWORD environment variable.
"""
import sys
import os
import argparse
import getpass
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
            logger.error("A user with that email or username already exists.")
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
        logger.info(f"Master user '{username}' created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a master administrator user")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--name", required=True, help="Full name")

    args = parser.parse_args()

    password = os.getenv("MASTER_PASSWORD") or getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)

    create_master_user(args.email, args.username, args.name, password)
