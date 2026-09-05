"""Add gst_percent to products (Product Master) - a default/
reference GST value only; historical Estimate/Order line items already
store their own tax_percent independently and are never affected by
changes to this.

Revision ID: 0051
Revises: 0050
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "products", sa.Column("gst_percent", sa.Numeric(5, 2), nullable=True, server_default="18"))


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("gst_percent")
