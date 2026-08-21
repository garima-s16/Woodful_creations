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

A third case, handled the same tolerant way as case 2: alembic_version
already exists (some earlier startup got at least partway through
history) but the physical schema has since drifted ahead of whatever
revision is stamped - e.g. a table created outside Alembic, a restored
backup, or an upgrade interrupted after creating a table but before its
transaction recorded the new alembic_version row. Previously this was
NOT tolerated at all - a plain `alembic upgrade head` was run with zero
error handling - so a single such collision anywhere in the remaining
chain was fatal on every subsequent startup, and fixing it by hand (e.g.
dropping the one colliding table) only exposed the next colliding table
on the following restart. That whole class of one-at-a-time failures is
what this module now prevents: every startup, not just the very first
one, walks forward one migration at a time and tolerates "already
applied" collisions.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
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


def _get_current_revision():
    """The revision stamped in the database's own alembic_version table,
    or None if there isn't one yet. Read directly rather than via
    alembic's `command.current` (which only prints to stdout/logging and
    doesn't hand the value back to the caller)."""
    if not _has_alembic_version_table():
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else None



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


def _upgrade_tolerating_legacy_schema(cfg: Config, from_revision: str = "base") -> None:
    """Walk every migration between from_revision and head, one at a
    time, applying it - and if a given step fails with the narrow
    "already exists" signature (see _is_already_applied_error), stamp it
    as done without re-running its body instead of raising.

    This used to only ever be called with from_revision="base", for a
    database with NO alembic_version tracking at all. That made the
    self-healing one-time-only: the very first startup against a fresh
    or legacy database was forgiving of a schema that didn't line up
    with the migration history, but every startup after that (once
    alembic_version existed) went through a plain command.upgrade(cfg,
    "head") with zero tolerance - so if the physical schema and the
    tracked revision ever drifted apart again for any reason (a table
    created by something other than Alembic, an interrupted upgrade, a
    restored backup, etc.), the very next migration whose create_table
    collided with an already-existing table would kill startup, and
    would keep doing so until that one table was manually dealt with -
    at which point the *next* colliding migration would do the same
    thing. That is the exact one-at-a-time pattern this function now
    prevents, by making every startup - not just the first - forgiving
    of a schema that's already ahead of what's stamped.

    from_revision is whatever the caller determined the database is
    actually at ("base" for no tracking at all, or a specific revision
    id read from alembic_version). If that id isn't one this codebase's
    migration chain recognizes (e.g. it was stamped by a different
    branch/version of the code), fall back to walking the entire chain
    from the very start - every step remains idempotent via the same
    try/except below, so replaying earlier migrations against a
    database that's actually already past them just hits more
    tolerated "already exists" collisions, never a real failure.
    """
    script = ScriptDirectory.from_config(cfg)
    try:
        ordered_revisions = list(script.walk_revisions(base=from_revision, head="head"))
    except Exception:
        logger.warning(
            "Stamped revision %r isn't part of this codebase's migration "
            "chain - walking the full chain from the beginning instead.",
            from_revision,
        )
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
        _upgrade_tolerating_legacy_schema(cfg, from_revision="base")
        logger.info("Database schema is up to date.")
        return

    # alembic_version already exists - but that only means SOME earlier
    # startup got this far, not that the physical schema still lines up
    # with whatever revision is stamped. It can drift out of sync again
    # after that point (a table created outside Alembic, a restored
    # backup, an upgrade that was interrupted after creating a table but
    # before its transaction committed the new alembic_version row,
    # etc.) - and previously, any such drift was fatal on every startup
    # from then on: a plain command.upgrade(cfg, "head") has no
    # tolerance for a single collision anywhere in the remaining chain,
    # so fixing one colliding table just exposed the next one on the
    # following restart. Walking forward from the stamped revision with
    # the same tolerance used for a brand-new legacy database closes that
    # gap - every startup self-heals, not just the first.
    current = _get_current_revision()
    _upgrade_tolerating_legacy_schema(cfg, from_revision=current or "base")
    logger.info("Database schema is up to date.")
