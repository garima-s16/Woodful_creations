"""LOCAL DATABASE -> NEON DATA MIGRATION.

This migrates the EXISTING Woodful business data currently in your
local database into Neon PostgreSQL. It is NOT demo-data seeding and
does not touch scripts/seed_sample_data.py's dataset in any way - this
tool only ever reads rows that are already in your real local database
and writes them, unchanged, to Neon.

============================================================
WHAT THIS DOES AND DOES NOT DO
============================================================
DOES:
  - Reads every row from every table in your local database (source).
  - Writes those exact rows into Neon (target), preserving primary
    keys, foreign keys, and all field values as-is.
  - Migrates tables in dependency order (parents before children -
    e.g. clients before estimates before estimate_line_items) so
    foreign key constraints are never violated mid-migration.
  - Resyncs every PostgreSQL sequence afterward, so the next row
    Woodful creates through the normal app gets an ID after the
    highest migrated ID, not a collision.
  - Requires you to type "MIGRATE" to confirm before writing anything.
  - Refuses to run if Neon already has data in it (see --force below).

DOES NOT:
  - Ever modify, delete, or truncate the local source database. Every
    operation against the source is a plain SELECT.
  - Ever run automatically - this is never called from app startup,
    only from this explicit script.
  - Ever seed/invent any data - only rows that already exist locally
    are migrated.
  - Regenerate any ID. Every primary key is preserved exactly.
  - Touch Google Drive or any file/document storage - see the "FILE
    REFERENCES" section this script prints at the end for what to
    check separately.

============================================================
TABLE CLASSIFICATION (inspected directly from app/models/, not assumed)
============================================================
Every table currently in Base.metadata is migrated by default, in
dependency order, EXCEPT:

  password_reset_tokens - excluded by default. Genuinely transient:
    short-lived, hash-only reset tokens (see PasswordResetToken's own
    docstring). Migrating expired tokens has no value. Include it
    anyway with --include-transient if you have a specific reason to.

Tables worth knowing about, included by default but with a different
character than typical business data (not excluded - just flagged
here honestly rather than silently treated as identical to `clients`
or `orders`):
  - id_sequences: backs the business_id counter (see
    app/utils/id_generator.py). Its OWN docstring says the table "has
    no meaning of its own" beyond its current position - migrated
    anyway (harmless) and its sequence is resynced like every other
    table.
  - notifications, automation_logs, integration_sync_logs,
    ai_workspace_reports: real historical/audit data per their own
    docstrings, but log-shaped (append-only, high row count, lower
    day-to-day business value than clients/orders/estimates). Included
    by default; safe to exclude with --exclude if you'd rather not
    carry log history into Neon on this first migration.
  - personal_cart_items: a per-user in-progress cart, not a completed
    business record. Included by default (harmless), flagged since
    it's more "current session state" than a permanent record.

============================================================
USAGE
============================================================
    python scripts/migrate_local_to_neon.py --dry-run
        Shows exactly what would be migrated (table order, row counts)
        without writing anything to Neon. Always run this first.

    python scripts/migrate_local_to_neon.py
        Runs the real migration. Prompts for typed "MIGRATE" confirmation.
        Refuses if Neon already has data (any table with rows) unless
        --force is also given.

    python scripts/migrate_local_to_neon.py --exclude notifications,automation_logs
        Skip specific tables beyond the default exclusion.

    python scripts/migrate_local_to_neon.py --resume
        Skips any table that already has ANY rows in Neon (assumes it
        migrated successfully already) and only migrates tables that
        are still empty on the Neon side. See "RESTART STRATEGY" below.

============================================================
RESTART STRATEGY
============================================================
This tool commits one table at a time (each table's full row set in
one transaction). If it fails partway through:
  - Every table BEFORE the failure is fully committed in Neon.
  - The failed table's transaction is rolled back - Neon has either
    ALL of that table's rows or NONE of them, never a partial set.
  - Every table AFTER the failure was never attempted.
  - The local source database is completely untouched regardless.

To resume: fix whatever caused the failure (see the error printed),
then re-run with --resume, which skips every table that already has
rows in Neon and picks up from the table that failed.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_EXCLUDED_TABLES = {"password_reset_tokens"}

# Local source database - deliberately NOT settings.DATABASE_URL, since
# that now points at Neon (per the user's already-verified connection).
# The local source is whatever SQLite file the app used before that
# switch - overridable via --source or LOCAL_DATABASE_URL, defaulting
# to the same default app/platform/configuration/config.py itself has always used.
DEFAULT_LOCAL_URL = "sqlite:///./woodful.db"


def _load_settings():
    try:
        from app.platform.configuration.config import settings
        return settings
    except ModuleNotFoundError as e:
        print(f"FAILED: could not import app settings - {e}")
        if "app" in str(e):
            print("The 'app' package itself could not be found. Run this from the backend/ directory.")
        else:
            print("A required Python package is missing - run this with the same venv/environment "
                  "the real backend uses.")
        sys.exit(1)


def _safe_identifier(url_str: str) -> str:
    """Host/database only, never credentials - same pattern already
    established in verify_migrations.py's verify_neon_connection() and
    inspect_neon_database.py."""
    from sqlalchemy.engine import make_url
    u = make_url(url_str)
    if u.drivername.startswith("sqlite"):
        return f"sqlite:{u.database}"
    return f"{u.host}/{u.database}" if u.database else str(u.host)


def _get_metadata():
    """Imports every model (registers them on Base.metadata) then
    returns Base.metadata.sorted_tables - SQLAlchemy's own topological
    sort of tables by foreign-key dependency. This is what determines
    migration order for all ~65 tables, rather than a hand-written
    order that would need updating every time a model changes."""
    from app.platform.database.database import Base
    from app import models  # noqa: F401 - registers every model on Base.metadata
    return Base.metadata


def _table_row_count(engine, table):
    from sqlalchemy import select, func
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar()


def _neon_has_any_data(engine, tables):
    for table in tables:
        if _table_row_count(engine, table) > 0:
            return table.name
    return None


def _resync_sequence(conn, table):
    """After inserting rows with explicit primary-key values, a
    PostgreSQL SERIAL/IDENTITY column's underlying sequence does NOT
    automatically know about them - it only advances on its own
    nextval() calls, which explicit-PK inserts never trigger. Without
    this, the very next row Woodful creates through the normal app
    could collide with a migrated ID. Only applies to single-column
    integer primary keys backed by a real Postgres sequence (checked
    via pg_get_serial_sequence, which returns NULL for anything else -
    e.g. this is skipped harmlessly for tables with no serial PK)."""
    from sqlalchemy import text
    pk_cols = list(table.primary_key.columns)
    if len(pk_cols) != 1:
        return None
    pk_name = pk_cols[0].name
    seq_row = conn.execute(text(
        f"SELECT pg_get_serial_sequence('{table.name}', '{pk_name}')"
    )).fetchone()
    seq_name = seq_row[0] if seq_row else None
    if not seq_name:
        return None
    conn.execute(text(
        f"SELECT setval('{seq_name}', COALESCE((SELECT MAX({pk_name}) FROM \"{table.name}\"), 1), "
        f"(SELECT MAX({pk_name}) FROM \"{table.name}\") IS NOT NULL)"
    ))
    return seq_name


def run(args) -> int:
    settings = _load_settings()
    neon_url = settings.DATABASE_URL
    local_url = args.source or os.environ.get("LOCAL_DATABASE_URL", DEFAULT_LOCAL_URL)

    if neon_url.startswith("sqlite"):
        print("FAILED: DATABASE_URL (the migration TARGET) is currently SQLite, not Neon/Postgres.")
        print("This tool migrates INTO whatever DATABASE_URL currently resolves to - "
              "confirm your .env/local.env has the Neon URL, same as python scripts/verify_migrations.py neon-connection verified.")
        return 1
    if local_url == neon_url:
        print("FAILED: source and target resolve to the same database. "
              "Pass --source explicitly if your local database isn't the default sqlite:///./woodful.db.")
        return 1

    from sqlalchemy import create_engine, text

    print("LOCAL -> NEON MIGRATION")
    print("=" * 60)
    print(f"Source (local):  {_safe_identifier(local_url)}")
    print(f"Target (Neon):   {_safe_identifier(neon_url)}")
    print()

    try:
        local_engine = create_engine(local_url)
        with local_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"FAILED: could not connect to the local source database - {type(e).__name__}")
        print(f"If your local database file isn't at the default location, pass --source "
              f"'sqlite:///<path to your .db file>'")
        return 1

    try:
        neon_engine = create_engine(neon_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with neon_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"FAILED: could not connect to Neon - {type(e).__name__}")
        return 1

    from sqlalchemy import inspect as sa_inspect

    metadata = _get_metadata()
    model_tables = list(metadata.sorted_tables)  # dependency order: parents before children, per the app's models

    # The actual local database may not have every table the current
    # models define - it may be an older database file that predates a
    # later migration/model addition (this is precisely the bug report
    # this fix addresses: attendance_statuses existed in the models but
    # not in the actual local .db file). Inspect what's REALLY there
    # rather than assume the models and the on-disk schema match.
    actual_local_table_names = set(sa_inspect(local_engine).get_table_names())
    tables_present_locally = [t for t in model_tables if t.name in actual_local_table_names]
    tables_missing_locally = [t.name for t in model_tables if t.name not in actual_local_table_names]

    excluded = set(DEFAULT_EXCLUDED_TABLES)
    if args.include_transient:
        excluded = set()
    if args.exclude:
        excluded |= {t.strip() for t in args.exclude.split(",") if t.strip()}

    tables_to_migrate = [t for t in tables_present_locally if t.name not in excluded]
    all_tables = model_tables  # kept for the summary line below

    print(f"Tables defined in the app's models: {len(model_tables)}")
    print(f"Tables that actually exist in the local database: {len(tables_present_locally)}")
    if tables_missing_locally:
        print(f"Tables the models define but that do NOT exist locally - SKIPPED, not migrated, not invented:")
        for name in tables_missing_locally:
            print(f"  {name}")
    print()
    print(f"Tables in dependency order ({len(tables_to_migrate)} of {len(all_tables)} total model tables, "
          f"{len(excluded)} excluded, {len(tables_missing_locally)} missing locally):")
    local_counts = {}
    for t in tables_to_migrate:
        count = _table_row_count(local_engine, t)
        local_counts[t.name] = count
        marker = "" if count else "  (empty locally - nothing to migrate for this table)"
        print(f"  {t.name:<30}{count:<10}{marker}")
    if excluded:
        print(f"\nExcluded: {', '.join(sorted(excluded))}")

    if args.dry_run:
        print("\n--dry-run: no connection writes were made, nothing was migrated.")
        return 0

    print()
    existing_data_table = _neon_has_any_data(neon_engine, tables_to_migrate) if not args.resume else None
    if existing_data_table and not args.force:
        print(f"REFUSED: Neon already has data (table '{existing_data_table}' has rows). "
              f"Re-run with --resume if this is a resumed migration, or --force if you "
              f"specifically intend to migrate on top of existing Neon data (NOT recommended "
              f"- existing rows are never overwritten, but a primary-key collision on any "
              f"table will fail that table's transaction).")
        return 1

    print("This will WRITE data into Neon. The local source database will NOT be modified.")
    confirm = input('Type MIGRATE to proceed, or anything else to cancel: ').strip()
    if confirm != "MIGRATE":
        print("Cancelled - nothing was written.")
        return 1

    print()
    migrated_counts = {}
    for t in tables_to_migrate:
        if args.resume and _table_row_count(neon_engine, t) > 0:
            print(f"{t.name:<30}SKIPPED (already has rows in Neon, --resume)")
            migrated_counts[t.name] = _table_row_count(neon_engine, t)
            continue
        if local_counts.get(t.name, 0) == 0:
            migrated_counts[t.name] = 0
            continue
        try:
            with local_engine.connect() as local_conn:
                rows = [dict(r._mapping) for r in local_conn.execute(t.select())]
            with neon_engine.begin() as neon_conn:
                if rows:
                    neon_conn.execute(t.insert(), rows)
                seq = _resync_sequence(neon_conn, t)
            migrated_counts[t.name] = len(rows)
            seq_note = f" (sequence resynced: {seq})" if seq else ""
            print(f"{t.name:<30}OK - {len(rows)} row(s) migrated{seq_note}")
        except Exception as e:
            print(f"{t.name:<30}FAILED - {type(e).__name__}: {e}")
            print(f"\nSTOPPED at '{t.name}'. Every table before this one is committed in Neon. "
                  f"The local source database was not modified. Fix the issue above, then "
                  f"re-run with --resume to continue from here.")
            return 1

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    total = sum(migrated_counts.values())
    print(f"Total rows migrated: {total}")
    print("\nRun 'python scripts/verify_migrations.py neon-data-match' next to compare local vs Neon counts.")

    file_ref_tables = [t for t in tables_to_migrate if any(
        "path" in c.name.lower() or "file" in c.name.lower() or "url" in c.name.lower() for c in t.columns
    )]
    if file_ref_tables:
        print(f"\nFILE/DOCUMENT REFERENCES - these tables have columns that look like file "
              f"paths or URLs, migrated as plain text values (not the actual files): "
              f"{', '.join(sorted(t.name for t in file_ref_tables))}. "
              f"If any of these point at local files, migrate those files to Google Drive "
              f"separately - this tool does not touch file storage at all.")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local Woodful data into Neon PostgreSQL.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing anything.")
    parser.add_argument("--source", help="Local source DATABASE_URL, if not the default sqlite:///./woodful.db")
    parser.add_argument("--exclude", help="Comma-separated table names to skip, in addition to the default exclusions.")
    parser.add_argument("--include-transient", action="store_true", help="Include password_reset_tokens too (excluded by default).")
    parser.add_argument("--force", action="store_true", help="Proceed even if Neon already has data.")
    parser.add_argument("--resume", action="store_true", help="Skip tables that already have rows in Neon; continue from where a previous run stopped.")
    sys.exit(run(parser.parse_args()))
