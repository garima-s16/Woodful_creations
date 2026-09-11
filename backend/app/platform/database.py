"""Database platform: SQLAlchemy engine/session/Base, the
BaseModel abstract base (id/created_at/updated_at), Alembic startup
auto-migration, and schema migration guard helpers. Combines the
former database.py, base.py, auto_migrate.py, and migration_guards.py."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.platform.config import settings
from sqlalchemy import Column, Integer, DateTime
from datetime import datetime
import logging
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic import op
import sqlalchemy as sa


# --- database.py ---
"""
Database Configuration and Session Management
"""

_engine_kwargs = {"echo": settings.DEBUG, "pool_pre_ping": True}


if not settings.DATABASE_URL.startswith("sqlite"):
    # SQLite's default pool implementation doesn't accept pool_size/max_overflow.
    _engine_kwargs.update(pool_size=10, max_overflow=20)


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base = declarative_base()


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- base.py ---
class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# --- auto_migrate.py ---
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
app/platform/database.py) - each one checks whether its own target
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

logger = logging.getLogger(__name__)


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


# --- migration_guards.py ---
"""Shared idempotency guards for Alembic migrations.

Root cause this exists to prevent: an existing database may have
tables/columns that a migration would still try to create from
scratch (e.g. if it was ever built via Base.metadata.create_all()
independently of Alembic's own tracking, or if a prior migration
attempt partially completed). Every migration's upgrade()/downgrade()
should use these instead of calling op.create_table/add_column/
create_index directly, so a create/add is always a genuine no-op (not
an error) when the target already exists.
"""

def table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def column_exists(bind, table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == name for c in insp.get_columns(table))


def index_exists(bind, table: str, name: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def create_table_if_missing(bind, name: str, *columns_and_constraints, **kw) -> bool:
    """Returns True if the table was actually created (so a caller can
    decide whether to also seed default rows into it), False if it
    already existed and nothing was done."""
    if table_exists(bind, name):
        return False
    op.create_table(name, *columns_and_constraints, **kw)
    return True


def add_column_if_missing(bind, table: str, column: sa.Column) -> bool:
    if column_exists(bind, table, column.name):
        return False
    # batch_alter_table, not a plain op.add_column: SQLite cannot add a
    # column with an inline ForeignKey via a normal ALTER TABLE ("No
    # support for ALTER of constraints in SQLite dialect") - it
    # requires a copy-and-rebuild, which batch mode handles. On
    # databases that support a real ALTER (Postgres/Neon) this behaves
    # identically to the plain call, so every existing caller of this
    # helper is unaffected either way.
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(column)
    return True


def create_index_if_missing(bind, index_name: str, table: str, columns, **kw) -> bool:
    if index_exists(bind, table, index_name):
        return False
    op.create_index(index_name, table, columns, **kw)
    return True


def column_is_integer_type(bind, table: str, column: str) -> bool:
    """True if the column's actual reflected type is an integer type
    (not yet converted to Numeric/Decimal). Used to guard a type
    ALTER (e.g. Integer -> Numeric) so it's only attempted when the
    column genuinely still needs it - unlike create_table/add_column,
    SQLite's batch-mode rebuild doesn't error on a redundant ALTER, but
    blindly re-asserting the WRONG existing_type (e.g. claiming
    Integer when the column is already Numeric, as it would be on a
    database built via create_all() against current models) risks
    Alembic generating a conversion inappropriate for data that's
    already the target type. Returns False (skip the alter) if the
    table or column doesn't exist at all, rather than raising."""
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    for col in insp.get_columns(table):
        if col["name"] == column:
            return isinstance(col["type"], sa.Integer)
    return False
