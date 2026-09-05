"""
Set (or reset) the password for an EXISTING Woodful user.

Companion to scripts/create_master_user.py (which only creates new
users) and scripts/seed_sample_login_data.py (which creates the five
named users with a safe, unusable placeholder password and never
touches the password of a user that already exists). This is the tool
for actually setting a real, usable password afterward.

Usage:
    python scripts/set_user_password.py --username garimas

If --password is omitted you'll be prompted interactively (not echoed)
- same safety note as create_master_user.py: prefer the prompt over a
plain CLI arg in a shared/logged shell.
"""
import argparse
import getpass
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platform.database.database import SessionLocal
from app.platform.security.security import hash_password
from app.modules.auth.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def set_password(username: str, password: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.error("No user found with username: %s", username)
            return False
        user.password_hash = hash_password(password)
        db.commit()
        logger.info("Password updated for user: %s", username)
        return True
    except Exception as e:
        db.rollback()
        logger.error("Error setting password: %s", e)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="Omit to be prompted interactively (recommended)")
    args = parser.parse_args()

    pw = args.password or getpass.getpass(f"Enter new password for user '{args.username}': ")
    set_password(args.username, pw)
