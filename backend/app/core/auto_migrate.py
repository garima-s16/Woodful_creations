"""Runs database migrations automatically on backend startup, instead of
requiring `alembic upgrade head` as a separate manual step.

Handles the one tricky case that a plain `alembic upgrade head` cannot
handle on its own: a database whose tables were created directly via
SQLAlchemy's create_all() (e.g. by scripts/setup_local.py, before a given
migration existed) rather than through Alembic. Such a database has no
alembic_version tracking table, so Alembic doesn't know it's already
"caught up" through some point in history - left alone, it would try to
re-run migration 0001 from scratch and fail with "table already exists".

This module detects that situation by checking for the specific
tables/columns each migration introduces, stamps the database at the
correct starting point, and only then runs the remaining migrations.
This makes the fix in code permanent: every future migration is applied
automatically the next time the backend starts, for this database and
for anyone else's, with no manual alembic command ever required again.
"""
import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import engine

logger = logging.getLogger(__name__)

# Each entry: (revision, a check that is True once that revision's
# changes are present in the database). Ordered oldest to newest.
_REVISION_CHECKS = [
    ("0001", lambda insp: insp.has_table("users")),
    ("0002", lambda insp: insp.has_table("estimates")),
    ("0003", lambda insp: insp.has_table("leaves")),
    ("0004", lambda insp: insp.has_table("client_activities")
     and any(c["name"] == "version" for c in insp.get_columns("estimates"))),
]


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def _has_alembic_version_table() -> bool:
    return inspect(engine).has_table("alembic_version")


def _detect_legacy_revision() -> Optional[str]:
    """For a database with real tables but no alembic_version tracking,
    find the latest revision whose changes are already present, so we
    can stamp there instead of re-running earlier migrations."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return None  # genuinely empty database - let migrations run from scratch

    latest_satisfied = None
    for revision, check in _REVISION_CHECKS:
        try:
            if check(insp):
                latest_satisfied = revision
        except Exception:
            break
    return latest_satisfied


def run_startup_migrations() -> None:
    cfg = _alembic_config()

    if not _has_alembic_version_table():
        legacy_revision = _detect_legacy_revision()
        if legacy_revision:
            logger.info(
                "Database has tables but no Alembic tracking (likely created via "
                "create_all before migration %s existed). Stamping at %s before upgrading.",
                legacy_revision, legacy_revision,
            )
            command.stamp(cfg, legacy_revision)

    command.upgrade(cfg, "head")
    logger.info("Database schema is up to date.")
