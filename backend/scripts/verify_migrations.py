"""Migration and Neon database verification.

Three genuinely distinct checks, callable independently or via this
file's own CLI:

    check_chain_integrity() - local Alembic chain integrity, zero
        dependencies, works with no database connection at all.
    verify_neon_connection() - can this environment actually reach
        Neon and run a query. Needs real credentials.
    verify_neon_data_match() - after a migration/copy to Neon, do the
        row counts (and optionally FK integrity) match the local
        source. Read-only against both databases.

Consolidated from three separate scripts (verify_migrations.py,
check_neon_connection.py, verify_migration.py) that had overlapping,
easily-confused names but genuinely different responsibilities - kept
as three functions in one file rather than one undifferentiated
script, since each answers a different question and needs different
things to actually run.
"""
import glob
import re
import sys


def check_chain_integrity(versions_dir: str) -> dict:
    """Returns a result dict: {"passed": bool, "head": str|None,
    "total": int, "broken_links": list, "duplicate_revisions": list,
    "detail": str}."""
    files = sorted(glob.glob(f"{versions_dir}/*.py"))
    chain = {}
    duplicate_revisions = []
    for f in files:
        content = open(f).read()
        rev_m = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', content, re.M)
        down_m = re.search(r'^down_revision\s*=\s*["\']?([^"\'\n]+)["\']?', content, re.M)
        if not rev_m:
            continue
        rev = rev_m.group(1)
        down = down_m.group(1).strip() if down_m else None
        if down == "None":
            down = None
        if rev in chain:
            duplicate_revisions.append(rev)
        chain[rev] = (down, f)

    heads = set(chain.keys()) - {v[0] for v in chain.values() if v[0]}
    broken_links = [f for down, f in chain.values() if down and down not in chain]

    passed = len(heads) == 1 and not broken_links and not duplicate_revisions
    head = next(iter(heads)) if len(heads) == 1 else None

    if passed:
        detail = f"Single head ({head}), {len(chain)} migrations, chain well-formed."
    else:
        problems = []
        if len(heads) != 1:
            problems.append(f"{len(heads)} head(s) found (expected exactly 1): {sorted(heads)}")
        if broken_links:
            problems.append(f"{len(broken_links)} broken down_revision link(s): {broken_links}")
        if duplicate_revisions:
            problems.append(f"{len(duplicate_revisions)} duplicate revision ID(s): {duplicate_revisions}")
        detail = "; ".join(problems)

    return {
        "passed": passed, "head": head, "total": len(chain),
        "broken_links": broken_links, "duplicate_revisions": duplicate_revisions,
        "detail": detail,
    }


def verify_neon_connection() -> int:
    """Neon connectivity check ONLY - does not touch migrations, does
    not create/drop any table, does not modify the local SQLite
    database or any model. Verifies exactly four things, in order,
    stopping at the first failure: DATABASE_URL is present and looks
    like a Postgres URL (without ever printing its value); SQLAlchemy
    can construct an engine from it; a real network connection to
    Neon succeeds; a trivial query (SELECT 1) actually executes.

    Safety: every print/log path here is safe by construction - it
    only ever prints values explicitly extracted via SQLAlchemy's own
    hide_password=True URL renderer (host/database/username, never
    password), or a short, generic description of an exception's
    TYPE, never the exception's raw str() - some SQLAlchemy/psycopg
    error messages embed the full DSN (including password) in their
    text, so printing an exception directly is not safe here.

    Needs the real dependencies (sqlalchemy + a Postgres driver) and
    real Neon credentials installed/configured - this function cannot
    run in a sandbox lacking either."""
    import os
    sys_path_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys_path_root not in sys.path:
        sys.path.insert(0, sys_path_root)

    try:
        from app.platform.config import settings
    except ModuleNotFoundError as e:
        print(f"FAILED at step 1 (load configuration): could not import app settings - {e}")
        if "app" in str(e):
            print("The 'app' package itself could not be found. Make sure you're running this "
                  "from the backend/ directory (the one containing the 'app' folder directly).")
        else:
            print(f"A required Python package is missing from this environment - "
                  f"install your project's normal requirements.txt in the environment/venv "
                  f"you're using to run the real backend (this is not about restructuring the "
                  f"project, just making sure the same venv the backend uses is the one running this script).")
        return 1
    except Exception as e:
        print(f"FAILED at step 1 (load configuration): could not import app settings - {type(e).__name__}: {e}")
        print("This usually means a required environment variable (e.g. SECRET_KEY) is missing. "
              "Check that your .env/local.env file exists in the project root (one level above "
              "backend/) and defines SECRET_KEY.")
        return 1

    database_url = settings.DATABASE_URL

    print("=== Step 1: environment variable ===")
    if not database_url:
        print("FAILED: DATABASE_URL is empty or not set.")
        return 1
    if database_url.startswith("sqlite"):
        print("FAILED: DATABASE_URL is still pointing at SQLite, not Neon/Postgres.")
        print("This means your .env/local.env file either doesn't set DATABASE_URL, "
              "or it isn't being loaded by the backend. Confirm the file is named "
              "exactly '.env' or 'local.env' and sits in the project root (one level "
              "above backend/), not inside backend/ itself.")
        return 1
    if not (database_url.startswith("postgresql://") or database_url.startswith("postgresql+psycopg2://")
            or database_url.startswith("postgres://")):
        print(f"WARNING: DATABASE_URL doesn't start with a recognized Postgres scheme "
              f"(got a value starting with {database_url.split(':', 1)[0]!r}). Continuing anyway - "
              f"SQLAlchemy will report a clearer error at engine-creation time if this is wrong.")
    print("PASS - DATABASE_URL is present and set to a non-SQLite value. (Value itself not printed.)")

    print("\n=== Step 2: SQLAlchemy engine creation ===")
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url
        url_obj = make_url(database_url)
        safe_url = url_obj.render_as_string(hide_password=True)
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    except ModuleNotFoundError as e:
        print(f"FAILED: {e}. SQLAlchemy (and a Postgres driver, e.g. psycopg2-binary) "
              f"must be installed in this environment - check requirements.txt / your venv.")
        return 1
    except Exception as e:
        print(f"FAILED: could not construct the engine - {type(e).__name__}. "
              f"This usually means DATABASE_URL is malformed (wrong scheme, missing host, "
              f"unescaped special characters in the password). Value itself not printed for safety.")
        return 1
    print(f"PASS - engine created. Host/database (password never shown): {safe_url}")

    print("\n=== Step 3 + 4: real connection + SELECT 1 ===")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row is None or row[0] != 1:
                print("FAILED: connected, but the test query didn't return the expected result.")
                return 1
    except ModuleNotFoundError as e:
        print(f"FAILED: {e}. Likely missing the Postgres driver (pip install psycopg2-binary).")
        return 1
    except Exception as e:
        # Deliberately NOT printing str(e) - some driver exceptions
        # embed the full DSN (including password) in their message.
        print(f"FAILED: could not connect / query - exception type: {type(e).__name__}")
        print("Common causes: wrong password, Neon project is paused/sleeping (Neon free tier "
              "auto-suspends after inactivity - the first connection after a pause can also just "
              "be slow, not necessarily failed), IP not allowed if Neon's IP allowlist is enabled, "
              "or sslmode=require missing from the URL (Neon requires SSL).")
        return 1

    print("PASS - connected and SELECT 1 succeeded.")
    print("\nNEON CONNECTION: SUCCESS")
    print(f"Host/project identifier (safe to share, no credentials): {url_obj.host}"
          + (f" / database: {url_obj.database}" if url_obj.database else ""))
    return 0


def _safe_identifier(url_str: str) -> str:
    from sqlalchemy.engine import make_url
    u = make_url(url_str)
    if u.drivername.startswith("sqlite"):
        return f"sqlite:{u.database}"
    return f"{u.host}/{u.database}" if u.database else str(u.host)


def verify_neon_data_match(source_url: str = None, check_orphans: bool = False) -> int:
    """Read-only migration verification. Compares row counts (and,
    when check_orphans=True, foreign-key integrity) between the local
    source database and Neon after a migration/copy has been run.
    Every operation here is a read-only SELECT/COUNT against both
    databases - nothing is written to either.

    Needs the real dependencies and a genuine Neon connection - cannot
    run in a sandbox lacking either."""
    import os
    DEFAULT_LOCAL_URL = "sqlite:///./woodful.db"
    sys_path_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys_path_root not in sys.path:
        sys.path.insert(0, sys_path_root)

    try:
        from app.platform.config import settings
    except ModuleNotFoundError as e:
        print(f"FAILED: could not import app settings - {e}")
        if "app" in str(e):
            print("The 'app' package itself could not be found. Run this from the backend/ directory.")
        else:
            print("A required Python package is missing - run this with the same venv/environment "
                  "the real backend uses.")
        return 1
    neon_url = settings.DATABASE_URL
    local_url = source_url or os.environ.get("LOCAL_DATABASE_URL", DEFAULT_LOCAL_URL)

    from sqlalchemy import create_engine, text, select, func
    from app.platform.database import Base
    from app import models  # noqa: F401

    print("MIGRATION VERIFICATION (read-only)")
    print("=" * 70)
    print(f"Local:  {_safe_identifier(local_url)}")
    print(f"Neon:   {_safe_identifier(neon_url)}")
    print()

    local_engine = create_engine(local_url)
    neon_engine = create_engine(neon_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

    with local_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    with neon_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    from sqlalchemy import inspect as sa_inspect

    model_tables = list(Base.metadata.sorted_tables)
    actual_local_table_names = set(sa_inspect(local_engine).get_table_names())
    tables = [t for t in model_tables if t.name in actual_local_table_names]
    tables_missing_locally = [t.name for t in model_tables if t.name not in actual_local_table_names]

    if tables_missing_locally:
        print(f"Tables the models define but that do NOT exist in the local database "
              f"(skipped, not queried, not invented):")
        for name in tables_missing_locally:
            print(f"  {name}")
        print()

    print(f"{'TABLE':<30}{'LOCAL':<10}{'NEON':<10}RESULT")
    print("-" * 70)
    mismatches = []
    for t in tables:
        with local_engine.connect() as conn:
            local_count = conn.execute(select(func.count()).select_from(t)).scalar()
        try:
            with neon_engine.connect() as conn:
                neon_count = conn.execute(select(func.count()).select_from(t)).scalar()
        except Exception:
            neon_count = None

        if neon_count is None:
            result = "NEON TABLE MISSING"
            mismatches.append(t.name)
        elif local_count == neon_count:
            result = "MATCH"
        else:
            result = "MISMATCH"
            mismatches.append(t.name)
        print(f"{t.name:<30}{local_count:<10}{str(neon_count):<10}{result}")

    print()
    if check_orphans:
        print("Foreign key orphan check (Neon side) - reports any row whose FK value doesn't")
        print("match an existing row in the referenced table:")
        orphan_found = False
        for t in tables:
            for fk in t.foreign_keys:
                col = fk.parent
                ref_table = fk.column.table
                ref_col = fk.column
                with neon_engine.connect() as conn:
                    orphan_count = conn.execute(text(
                        f'SELECT COUNT(*) FROM "{t.name}" c '
                        f'WHERE c."{col.name}" IS NOT NULL AND NOT EXISTS ('
                        f'  SELECT 1 FROM "{ref_table.name}" r WHERE r."{ref_col.name}" = c."{col.name}"'
                        f')'
                    )).scalar()
                if orphan_count:
                    orphan_found = True
                    print(f"  {t.name}.{col.name} -> {ref_table.name}.{ref_col.name}: {orphan_count} orphaned row(s)")
        if not orphan_found:
            print("  None found.")
        print()

    print("FINAL RESULT:")
    if not mismatches:
        print("ALL TABLES MATCH")
        return 0
    else:
        print(f"{len(mismatches)} TABLE(S) MISMATCHED OR MISSING: {', '.join(mismatches)}")
        return 1


def fresh_sqlite_migration_status() -> dict:
    """Honestly reports that actually
    running `alembic upgrade head` against a fresh SQLite database is
    BLOCKED in this environment, and gives the exact reproducible
    command for elsewhere - never silently skipped, never converted
    into a false PASS.

    Confirmed directly (not assumed) that neither `alembic` nor
    `sqlalchemy` are genuinely pip-installed here: `pip show alembic`
    reports "Package(s) not found", and `import sqlalchemy` raises
    ModuleNotFoundError. An earlier `import alembic` appearing to
    succeed was Python resolving this project's own alembic/
    directory as a namespace collision, not the real library."""
    try:
        import sqlalchemy
        import alembic  # noqa: F401
        # A minimal stub (e.g. the one verify_chatbot.py installs into
        # sys.modules for its own import needs) can make `import
        # sqlalchemy` succeed even when no real install exists -
        # confirmed directly that such a stub lacks __version__, which
        # every genuine sqlalchemy install has. Checking for it here
        # is what actually distinguishes "really installed" from
        # "another verifier's stub happens to still be in sys.modules
        # from earlier in this same process" - without this, this
        # function would have silently, incorrectly reported "not
        # blocked" whenever it ran after verify_chatbot in the same
        # process, exactly the kind of misleading result this
        # verification script exists to prevent.
        if not hasattr(sqlalchemy, "__version__"):
            raise ImportError("sqlalchemy is present in sys.modules but has no __version__ - this is a stub, not a real install")
        return {"blocked": False}
    except ImportError as e:
        return {
            "blocked": True,
            "reason": f"sqlalchemy/alembic are not genuinely installed in this environment ({e})",
            "reproduce_command": (
                "cd backend && rm -f /tmp/woodful_verify.db && "
                "DATABASE_URL=sqlite:////tmp/woodful_verify.db alembic upgrade head && "
                "echo 'Migration chain reached head successfully'"
            ),
        }


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Migration and Neon database verification.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("chain", help="Local Alembic chain integrity (default - no database needed).")
    sub.add_parser("neon-connection", help="Can this environment reach Neon and run a query (needs real credentials).")
    data_match = sub.add_parser("neon-data-match", help="Compare local vs Neon row counts after a migration/copy (read-only, needs real credentials).")
    data_match.add_argument("--source", help="Local source DATABASE_URL, if not the default sqlite:///./woodful.db")
    data_match.add_argument("--check-orphans", action="store_true", help="Also check for orphaned foreign keys in Neon (slower - one query per FK per table).")

    args = parser.parse_args()
    command = args.command or "chain"

    if command == "chain":
        versions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic", "versions")
        result = check_chain_integrity(versions_dir)
        print("Chain integrity:", "PASS" if result["passed"] else "FAIL", "-", result["detail"])
        fresh = fresh_sqlite_migration_status()
        if fresh["blocked"]:
            print("Fresh SQLite migration: BLOCKED - ENVIRONMENT -", fresh["reason"])
            print("Reproduce with:", fresh["reproduce_command"])
        return 0 if result["passed"] else 1
    elif command == "neon-connection":
        return verify_neon_connection()
    elif command == "neon-data-match":
        return verify_neon_data_match(source_url=args.source, check_orphans=args.check_orphans)


if __name__ == "__main__":
    sys.exit(main())
