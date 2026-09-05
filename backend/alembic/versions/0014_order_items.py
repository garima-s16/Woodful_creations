"""Add OrderItem (Priority 1B) - a proper scope/items breakdown for an
order, the same pattern as EstimateLineItem (migration 0011). Each item
carries description/category/quantity/unit/rate/amount and an optional
source_estimate_item_id, so items copied in when an order is created
from an estimate stay traceable back to the estimate line they came
from, without duplicating unrelated data.

A fresh CREATE TABLE, which natively supports its two foreign keys
without any SQLite ALTER TABLE limitation.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("source_estimate_item_id", sa.Integer(), sa.ForeignKey("estimate_line_items.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("order_items")
