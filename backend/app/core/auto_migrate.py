"""Runs database migrations automatically on backend startup, instead of
requiring `alembic upgrade head` as a separate manual step.

Handles the tricky case that a plain `alembic upgrade head` cannot handle
on its own: a database whose tables were created directly via
SQLAlchemy's create_all() (e.g. by an old run of scripts/seed_sample_data.py,
which used to call Base.metadata.create_all(bind=engine) before seeding -
that call has since been removed; see that script) rather than through
Alembic. Such a database has no alembic_version tracking table, so
Alembic doesn't know it's already "caught up" through some point in
history - left alone, it would try to re-run migration 0001 from scratch
and fail with "table already exists".

There are two distinct shapes this can take, handled differently:

1. The database has EVERY table today's models define (a create_all() run
   against the current codebase). This is unambiguous - it already has
   everything any migration, old or new, would create - so it's always
   safe and correct to stamp it straight at head. See
   _database_already_matches_current_models.

2. The database has SOME tables but not all of today's - a genuinely
   older/partial legacy state (create_all() run against an older version
   of the models, or an old database that lost its alembic_version row).
   There is no way to know in advance exactly which revision that
   corresponds to, so instead of guessing a single starting point from a
   hardcoded list of table/column checks (which is what this module used
   to do, and which only ever recognised revisions 0001-0004 - silently
   and unsafely wrong for any database that had progressed further than
   that but wasn't fully current either), this walks every migration in
   order, one at a time, and adopts whatever the database already has:
   if a given revision's own change is already present, it's stamped as
   done without re-running it; otherwise it's actually applied. This is
   self-maintaining - it never needs a hardcoded list updated as new
   migrations are added - and correct regardless of how far along the
   legacy database happens to be.

Either way, once the database is caught up to a known revision, the
remaining migrations run normally. This makes the fix in code permanent:
every future migration is applied automatically the next time the
backend starts, with no manual alembic command ever required.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.database import engine

logger = logging.getLogger(__name__)

# The narrow, specific signature of "this schema object already exists" -
# covers both SQLite ("table X already exists", "duplicate column name: X")
# and Postgres ("relation \"X\" already exists", "column \"X\" ... already
# exists"). Deliberately narrow: anything else (a missing table a later
# migration assumed, a genuinely malformed migration, a locked database,
# etc.) must NOT match this and must propagate as a real, fatal failure -
# see _is_already_applied_error.
_ALREADY_APPLIED_MARKERS = ("already exists", "duplicate column")


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def _has_alembic_version_table() -> bool:
    return inspect(engine).has_table("alembic_version")


def _get_head_revision(cfg: Config) -> str:
    """The actual current head, read from the migration scripts
    themselves - never hardcoded, so this stays correct automatically
    as new migrations are added, with no manual update ever required
    here again."""
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()


def _database_already_matches_current_models(insp) -> bool:
    """True if every table the application's current SQLAlchemy models
    define already exists in the database - the exact signature of a
    database created via Base.metadata.create_all() against today's
    models, rather than incrementally through Alembic. Such a database
    already has everything any migration - old or new - would create, so
    it is always safe and correct to stamp it at the real head rather
    than an intermediate revision."""
    # Imported here, not at module level - avoids a real risk of a
    # circular import (app.core.database, which this module already
    # imports, is itself imported by the model modules).
    from app.models.base import Base
    from app import models  # noqa: F401 - ensures every model registers on Base.metadata

    existing_tables = set(insp.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    return expected_tables.issubset(existing_tables)


def _is_already_applied_error(exc: Exception) -> bool:
    """True only for the narrow "this table/column/index already exists"
    signature - see _ALREADY_APPLIED_MARKERS. Anything else (including any
    OperationalError/ProgrammingError with a different message) is a
    genuine migration failure and must NOT be treated as "already
    applied"."""
    root = getattr(exc, "orig", None) or exc
    message = str(root).lower()
    return any(marker in message for marker in _ALREADY_APPLIED_MARKERS)


def _upgrade_tolerating_legacy_schema(cfg: Config) -> None:
    """For a database with SOME tables but not the full current set, and
    no alembic_version tracking: walk every migration from the very
    beginning, one at a time. For each one, try to actually apply it; if
    it fails with the narrow "already exists" signature, that migration's
    change is already reflected in the schema (left over from however this
    database was originally created) - stamp it as done without
    re-running its body, log it, and move on to the next. Any other error
    is a genuine migration bug and propagates, failing startup loudly
    rather than leaving a half-migrated database silently marked as fine.

    Applying one target revision at a time (rather than jumping straight
    to head) means each step only ever needs to apply the single delta
    since the last successful step, so a conflict on migration N doesn't
    block migrations N+1..head from being evaluated and applied on their
    own merits afterward.
    """
    script = ScriptDirectory.from_config(cfg)
    ordered_revisions = list(script.walk_revisions(base="base", head="head"))
    ordered_revisions.reverse()  # oldest first

    for rev in ordered_revisions:
        try:
            command.upgrade(cfg, rev.revision)
        except (OperationalError, ProgrammingError) as exc:
            if not _is_already_applied_error(exc):
                raise
            logger.warning(
                "Migration %s ('%s') is already reflected in the database "
                "schema (%s). Stamping it as applied without re-running "
                "it, and continuing to the next migration.",
                rev.revision, rev.doc, exc.__class__.__name__,
            )
            command.stamp(cfg, rev.revision)


def run_startup_migrations() -> None:
    cfg = _alembic_config()

    if not _has_alembic_version_table():
        insp = inspect(engine)

        if not insp.has_table("users"):
            # Genuinely empty database - nothing to detect, just run
            # every migration from scratch.
            command.upgrade(cfg, "head")
            logger.info("Database schema is up to date.")
            return

        if _database_already_matches_current_models(insp):
            head = _get_head_revision(cfg)
            logger.info(
                "Database has every table today's models define but no "
                "Alembic tracking (likely created via create_all() "
                "against the current codebase). Stamping at head (%s) "
                "rather than replaying every migration.", head,
            )
            command.stamp(cfg, head)
            logger.info("Database schema is up to date.")
            return

        logger.info(
            "Database has tables but no Alembic tracking, and does not "
            "match today's full model set (an older/partial legacy "
            "database). Walking every migration from the beginning and "
            "adopting whatever the schema already reflects."
        )
        _upgrade_tolerating_legacy_schema(cfg)
        logger.info("Database schema is up to date.")
        return

    command.upgrade(cfg, "head")
    logger.info("Database schema is up to date.")
