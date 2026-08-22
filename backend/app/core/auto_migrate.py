"""Runs database migrations automatically on backend startup, instead of
requiring `alembic upgrade head` as a separate manual step.

ARCHITECTURE (rewritten): this module used to try to GUESS which
revision a database with no alembic_version table was already "caught
up" through, by checking for a handful of specific tables/columns, and
then stamping the database at that guessed revision before running the
rest. That was unsafe for two reasons:

  1. The check list only covered the first few migrations (0001-0004).
     A database with a much newer schema (e.g. created via
     Base.metadata.create_all() against today's models, which builds
     EVERY current table at once, not just the first few) would still
     get misdiagnosed as "caught up through 0004" and then have every
     later migration replayed against tables that already exist,
     failing with "table/column already exists".

  2. More fundamentally: stamping a GUESSED revision, even a more
     careful guess, can silently paper over a real schema mismatch
     instead of surfacing it. If the guess is wrong, later migrations
     get skipped that should have run, or replayed when they
     shouldn't - and there is no way to tell from the stamp alone.

The fix is not a better guess. It is to stop guessing: every migration
in this project is written to be idempotent (see
app/core/migration_guards.py) - each one checks whether its own target
table/column/row already exists before creating it, so it is always
safe to actually RUN, never just skip. That means Alembic can walk the
ENTIRE chain from the very beginning against ANY existing database
state - genuinely empty, partially built by create_all(), fully
current, or anything in between - and each migration will correctly
no-op past whatever is already present and apply only what is
genuinely missing. No revision needs to be guessed or stamped ahead of
running upgrade(); Alembic stamps the real, correct revision itself
once the chain actually completes.

If a migration genuinely cannot proceed (a real conflict, not just an
already-satisfied target), it raises - and this module lets that
propagate rather than stamping over it, so the operator gets a clear
error pointing at the actual problem instead of a silently-degraded
database.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def run_startup_migrations() -> None:
    """Runs the full migration chain unconditionally. Every migration
    is idempotent, so this is safe and correct regardless of the
    database's starting state - see the module docstring above for why
    this replaces the old guess-and-stamp approach entirely."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    logger.info("Database schema is up to date.")
