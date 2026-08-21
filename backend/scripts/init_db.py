"""
Applies all database migrations. This used to call create_all() directly,
which could not add new columns/tables to a database that already
existed - see app/core/auto_migrate.py for the fix. Kept as a thin
wrapper for anyone with this command memorized; scripts/setup_local.py
does the same thing plus the interactive admin-creation step.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.auto_migrate import run_startup_migrations
from app import models  # noqa: F401 - registers every model on Base.metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    logger.info("Applying database migrations...")
    run_startup_migrations()
    logger.info("Database is up to date.")


if __name__ == "__main__":
    init_database()
    logger.info(
        "Done. Create your first admin user with: "
        "python scripts/create_master_user.py --email you@example.com --username you --name \"Your Name\""
    )
