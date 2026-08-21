"""Add real estimate line items (EstimateLineItem) and a discount field
on Estimate. Previously an estimate had only two flat cost fields
(material_cost, labor_cost) - this adds a proper itemized line, each
with its own description/category/quantity/unit/rate/amount, so an
estimate can actually itemize what's being quoted (Wardrobe, Hardware,
Installation, ...) instead of one lump sum.

material_cost/labor_cost are kept (not dropped) for backward
compatibility with estimates created before this migration - no data
is deleted, and old records remain fully readable with their existing
values.

discount is a plain nullable-with-default column with no inline
constraint, so - same reasoning as prior migrations that added simple
columns - SQLite's ALTER TABLE can add it directly without needing
batch mode. estimate_line_items is a fresh CREATE TABLE, which
natively supports its foreign key without any SQLite limitation.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estimates", sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"))

    op.create_table(
        "estimate_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("estimate_line_items")
    op.drop_column("estimates", "discount")
