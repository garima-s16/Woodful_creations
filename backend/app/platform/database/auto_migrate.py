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
app/platform/database/migration_guards.py) - each one checks whether its own target
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

from app.platform.configuration.config import settings

logger = logging.getLogger(__name__)

# An arbitrary, fixed 64-bit key unique to this app's startup-migration
# lock - PostgreSQL advisory locks are identified by number, not name;
# this value has no meaning beyond being unlikely to collide with any
# other advisory lock this application (or another one sharing the
# same database) might take out for a different purpose.
_MIGRATION_LOCK_KEY = 8825170392  # arbitrary, fixed - see comment above


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def run_startup_migrations() -> None:
    """Runs the full migration chain unconditionally. Every migration
    is idempotent, so this is safe and correct regardless of the
    database's starting state - see the module docstring above for why
    this replaces the old guess-and-stamp approach entirely.

    On PostgreSQL, the actual upgrade() call is
    wrapped in a session-level advisory lock (pg_advisory_lock) keyed to
    this app specifically, so if multiple backend instances start at
    once (a horizontally-scaled deployment), only one genuinely runs the
    chain at a time - the others block on acquiring the lock, then once
    they get it, the chain is already at head and every migration
    no-ops through quickly. This does not change migration history or
    reseed/reset any data - it only serializes who is allowed to run
    upgrade() at the same moment. Skipped for SQLite (tests, local dev),
    which has no advisory-lock concept and a different concurrency
    model entirely - single-process local use was never the scenario
    this protects against."""
    cfg = _alembic_config()

    if settings.DATABASE_URL.startswith("sqlite"):
        command.upgrade(cfg, "head")
        logger.info("Database schema is up to date.")
        return

    import sqlalchemy as sa
    engine = sa.create_engine(settings.DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
            try:
                command.upgrade(cfg, "head")
                logger.info("Database schema is up to date.")
            finally:
                conn.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY})
    finally:
        engine.dispose()
