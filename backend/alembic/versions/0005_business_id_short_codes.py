"""Add business_id (10-character opaque alphanumeric external identifier)
to every user-facing business entity - Client, Employee, Material,
Supplier, Estimate, Order, Payment, Purchase, DailyTask, ProductionJob,
ProjectExpense. Coexists with the existing sequential *_code fields
rather than replacing them.

Unlike migration 0004, this does NOT need batch mode: that migration
added a column with an inline foreign key, which SQLite's ALTER TABLE
cannot do directly. This column has no inline constraint - it's a
plain nullable column, and the uniqueness is enforced by a separate
CREATE UNIQUE INDEX statement, which SQLite supports natively. This is
the same proven-safe pattern migration 0002 already used for adding
plain columns to existing tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing, create_index_if_missing

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = [
    "clients", "employees", "materials", "suppliers", "estimates", "orders",
    "payments", "purchases", "daily_tasks", "production_jobs", "project_expenses",
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        add_column_if_missing(bind, table, sa.Column("business_id", sa.String(10), nullable=True))
        create_index_if_missing(bind, f"ix_{table}_business_id", table, ["business_id"], unique=True)


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_business_id", table_name=table)
        op.drop_column(table, "business_id")
