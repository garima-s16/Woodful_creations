"""
One-step local setup: applies all database migrations (self-healing even
against a database created by an older version of this script - see
app/platform/database/auto_migrate.py for how), then checks whether any master user
exists yet - if not, walks you through creating one interactively right
here (no hardcoded credentials, ever).

Usage:
    python scripts/setup_local.py

Safe to re-run: migrations are idempotent, and this skips the
admin-creation prompt if a master user is already present.
"""
import getpass
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platform.database import SessionLocal
from app.platform.database import run_startup_migrations
from app import models  # noqa: F401
from app.modules.auth.auth import User
from scripts.create_master_user import create_master_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Applying database migrations...")
    run_startup_migrations()
    logger.info("Database ready.")

    db = SessionLocal()
    try:
        has_master = db.query(User).filter(User.role == "master", User.is_deleted.is_(False)).first()
    finally:
        db.close()

    if has_master:
        logger.info("A master user already exists (%s) - skipping admin creation.", has_master.username)
        logger.info("Setup complete.")
        return

    print("\nNo master (admin) account exists yet. Let's create one now.")
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password (not shown): ")

    if create_master_user(email, username, full_name, password):
        print(f"\nDone. You can now log in as '{username}'.")
    else:
        print("\nSomething went wrong creating the account - check the log output above.")


if __name__ == "__main__":
    main()
