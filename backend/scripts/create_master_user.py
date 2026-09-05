"""
Create a master (admin) user.

Usage:
    python scripts/create_master_user.py --email you@example.com --username you --name "Your Name"

If --password is omitted you'll be prompted for one interactively (not echoed).
Never pass real passwords as a plain CLI arg in a shared/logged shell if you
can avoid it - prefer the interactive prompt.
"""
import argparse
import getpass
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.exc import IntegrityError

from app.platform.database.database import SessionLocal
from app.platform.security.security import hash_password
from app.modules.auth.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_master_user(email: str, username: str, full_name: str, password: str) -> bool:
    db = SessionLocal()
    try:
        exists = db.query(User).filter((User.email == email) | (User.username == username)).first()
        if exists:
            logger.info("User already exists: %s", username)
            return False

        user = User(
            email=email,
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            is_active=True,
            role="master",
        )
        db.add(user)
        db.commit()
        logger.info("Master user created: %s", username)
        return True
    except IntegrityError as e:
        db.rollback()
        logger.error("Integrity error: %s", e)
        return False
    except Exception as e:
        db.rollback()
        logger.error("Error creating user: %s", e)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--name", required=True, dest="full_name")
    parser.add_argument("--password", help="Omit to be prompted interactively (recommended)")
    args = parser.parse_args()

    pw = args.password or getpass.getpass(f"Enter password for user '{args.username}': ")
    create_master_user(args.email, args.username, args.full_name, pw)
