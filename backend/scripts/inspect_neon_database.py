"""Read-only Neon database inspection.

Every operation in this script is read-only: schema reflection
(inspect()), COUNT(*) queries, and a SELECT against alembic_version.
Nothing here can create, alter, or delete anything - there is no
INSERT/UPDATE/DELETE/DDL statement anywhere in this file.

Table-name mapping note, stated honestly rather than guessed silently:
two of the requested entities don't have a literal matching table in
this codebase's actual models (checked app/models/*.py directly before
writing this script, not assumed):
  - "inventory" -> no Inventory table exists. stock_ledger_entries is
    the closest real match (a per-movement stock ledger); Material's
    own current_stock/opening_stock/minimum_stock columns are the
    other place stock data actually lives.
  - "projects" -> no Project table exists. Orders serve this role
    directly (project_status/project_type are columns on the Order
    table itself) - there is no separate Projects entity to count.
Both are shown in the output with a note explaining this, not silently
skipped and not force-mapped to something misleading.

Usage (from the backend/ directory, on the machine with the real Neon
connection already verified working):
    python scripts/inspect_neon_database.py
"""
import sys
import os

# Same fix as verify_migrations.py's verify_neon_connection(), scripts/seed_sample_data.py,
# and alembic/env.py - makes `app` importable when this file is run
# directly from backend/, no PYTHONPATH manipulation required.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# (table_label, real_table_name_or_None, note_if_none)
ENTITY_TABLES = [
    ("clients", "clients", None),
    ("suppliers", "suppliers", None),
    ("products", "products", None),
    ("product_materials", "product_materials", None),
    ("materials", "materials", None),
    ("employees", "employees", None),
    ("estimates", "estimates", None),
    ("estimate_line_items", "estimate_line_items", None),
    ("orders", "orders", None),
    ("order_items", "order_items", None),
    ("payments", "payments", None),
    ("inventory", "stock_ledger_entries", "no dedicated Inventory table - closest match is the stock ledger"),
    ("projects", None, "no dedicated Projects table - Orders serve this role directly"),
    ("users", "users", None),
    ("audit records", "audit_logs", None),
]


def main() -> int:
    try:
        from app.platform.config import settings
    except ModuleNotFoundError as e:
        print(f"FAILED at step 1 (load configuration): could not import app settings - {e}")
        if "app" in str(e):
            print("The 'app' package itself could not be found. Run this from the backend/ directory.")
        else:
            print("A required Python package is missing - run this with the same venv/environment "
                  "the real backend uses.")
        return 1

    database_url = settings.DATABASE_URL
    if database_url.startswith("sqlite"):
        print("FAILED: DATABASE_URL is set to SQLite, not Neon/Postgres. "
              "This inspects whatever DATABASE_URL currently resolves to - "
              "confirm your .env/local.env is being loaded correctly (same check "
              "python scripts/verify_migrations.py neon-connection already verified for you).")
        return 1

    try:
        from sqlalchemy import create_engine, text, inspect
        from sqlalchemy.engine import make_url
        url_obj = make_url(database_url)
        safe_db_identifier = f"{url_obj.host}/{url_obj.database}" if url_obj.database else url_obj.host
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    except Exception as e:
        print(f"FAILED: could not construct the engine - {type(e).__name__}")
        return 1

    print("NEON DATABASE INSPECTION")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Connection: FAILED - {type(e).__name__}")
        print("(exception message not shown - may contain connection details)")
        return 1

    print("Connection: SUCCESS")
    print(f"Database: {safe_db_identifier}")

    # Alembic revision - read-only SELECT against alembic_version, the
    # standard table Alembic itself creates and maintains. If it
    # doesn't exist yet, that's itself meaningful information (no
    # migration has ever been stamped/run against this database) -
    # reported plainly, not treated as an error.
    inspector = inspect(engine)
    all_tables = set(inspector.get_table_names())

    if "alembic_version" in all_tables:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            alembic_revision = row[0] if row else "(alembic_version table exists but is empty)"
    else:
        alembic_revision = "NONE - alembic_version table does not exist (no migration has been stamped/run here yet)"
    print(f"Alembic revision: {alembic_revision}")

    print()
    print(f"{'TABLE':<30}{'ROW COUNT':<15}NOTES")
    print("-" * 70)

    any_table_exists = False
    any_data_exists = False
    for label, real_table, note in ENTITY_TABLES:
        if real_table is None:
            print(f"{label:<30}{'N/A':<15}{note}")
            continue
        if real_table not in all_tables:
            print(f"{label:<30}{'(no table)':<15}{note or ''}")
            continue
        any_table_exists = True
        try:
            with engine.connect() as conn:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{real_table}"')).scalar()
            if count and count > 0:
                any_data_exists = True
            note_text = note or (f"table: {real_table}" if real_table != label else "")
            print(f"{label:<30}{count:<15}{note_text}")
        except Exception as e:
            print(f"{label:<30}{'ERROR':<15}{type(e).__name__}")

    print()
    print("FINAL STATUS:")
    print(f"SCHEMA: {'PRESENT' if any_table_exists else 'ABSENT - no Woodful application tables found'}")
    if not any_table_exists:
        print("DATA: N/A (no schema present)")
    elif any_data_exists:
        print("DATA: PARTIAL/PRESENT (at least one table has rows - see counts above for exactly which)")
    else:
        print("DATA: EMPTY (every existing table has zero rows)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
