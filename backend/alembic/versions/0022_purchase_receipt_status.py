"""Add Purchase.receipt_status - distinguishes "ordered, not yet
received" from "received" (stock increases only on the latter),
matching the explicit principle that a purchase order must not increase
stock by itself. Defaults to "Received" for every existing row, so
existing purchases (which were always immediately-received under the
old single-step model) are correctly represented, and nothing about
current behavior changes unless a caller explicitly opts into "Ordered".

Simple ADD COLUMN, no inline FK - the SQLite batch_alter_table pattern
established in earlier migrations was specifically for FK constraints,
not needed here.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchases",
        sa.Column("receipt_status", sa.String(20), nullable=False, server_default="Received"),
    )


def downgrade() -> None:
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.drop_column("receipt_status")
