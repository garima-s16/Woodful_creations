"""Backfill business_id for every pre-existing row created before migrations
0005/0006 added the column (those two only added it as nullable, since a
NOT NULL column can't be added to a table that already has rows without a
value to put in them). This migration:

  1. Finds every row where business_id IS NULL, across all 15 business
     entities, and assigns it a fresh random 10-character ID using the
     same generator the application uses for new rows (app.platform.database.id_generator
     generate_short_id) - one reusable generator, not reimplemented here.
  2. Retries on collision, same as the application code does.
  3. Only after every row has a value, alters the column to NOT NULL, so the
     invariant "business_id is never NULL" is actually enforced by the
     database from this point forward - not just true by convention.

Uses batch mode for the NOT NULL alter since SQLite cannot ALTER COLUMN a
constraint change in place (same reasoning as migration 0004's batch use
for inline-FK columns) - batch mode is a correct no-op-equivalent on
Postgres/MySQL too, so this migration is safe on both backends.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

from app.platform.database.id_generator import generate_short_id
from app.platform.database.migration_guards import column_exists

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = [
    "clients", "employees", "materials", "suppliers", "estimates", "orders",
    "payments", "purchases", "daily_tasks", "production_jobs", "project_expenses",
    "candidates", "interviews", "leaves", "attendance",
]


def upgrade() -> None:
    bind = op.get_bind()

    for table in TABLES:
        # Do not assume business_id already exists on every table here -
        # it's added by migrations 0005/0006, not this one. If it's
        # genuinely missing for some reason, skip that table rather
        # than crash with "no such column" - this migration's job is
        # backfilling values and enforcing NOT NULL, not creating the
        # column itself.
        if not column_exists(bind, table, "business_id"):
            continue
        rows = bind.execute(sa.text(f"SELECT id FROM {table} WHERE business_id IS NULL")).fetchall()
        for (row_id,) in rows:
            # Retry-on-collision, matching generate_unique_code's documented
            # pattern - the unique index makes a collision self-evident via
            # IntegrityError, extremely unlikely (36^10 space) but handled.
            # Each attempt runs inside its own SAVEPOINT so a failed attempt
            # only rolls back that one UPDATE, not the whole migration
            # transaction (a plain try/except around bind.execute would
            # otherwise poison the entire transaction on Postgres).
            for attempt in range(5):
                candidate_id = generate_short_id()
                try:
                    with bind.begin_nested():
                        bind.execute(
                            sa.text(f"UPDATE {table} SET business_id = :bid WHERE id = :rid"),
                            {"bid": candidate_id, "rid": row_id},
                        )
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    continue

    for table in TABLES:
        if not column_exists(bind, table, "business_id"):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        if not column_exists(bind, table, "business_id"):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=True)
