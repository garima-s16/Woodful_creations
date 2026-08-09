import getpass
import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.db import SessionLocal
from app.models import User
# Placeholder hash function - replace with project hash utility
def hash_password(pw):
    import hashlib
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

import logging
from sqlalchemy.exc import IntegrityError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_master_user(email: str, username: str, full_name: str, password: str):
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
            hashed_password=hash_password(password),
            is_active=True,
            is_master=True,
            role="master",
            cannot_be_deleted=True
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
    parser.add_argument("--email", help="email")
    parser.add_argument("--username", help="username")
    parser.add_argument("--name", help="full name")
    parser.add_argument("--password", help="password (optional)")
    args = parser.parse_args()
    if not args.password:
        pw = getpass.getpass("Enter password for user '{}': ".format(args.username or "new user"))
    else:
        pw = args.password
    create_master_user(args.email, args.username, args.name, pw)
