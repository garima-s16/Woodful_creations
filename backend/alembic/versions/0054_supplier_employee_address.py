"""Add a proper address column to suppliers and employees, so the
permanent Woodful roster address can be displayed in the Supplier/
Employee UI directly instead of being packed into remarks.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "suppliers", sa.Column("address", sa.Text(), nullable=True))
    add_column_if_missing(bind, "employees", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("employees", "address")
    op.drop_column("suppliers", "address")
