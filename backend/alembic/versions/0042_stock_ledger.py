"""Add stock_ledger_entries - the real source-of-truth transaction
log for an explicitly-flagged "major architectural priority".
Immutable, append-only. current_stock remains the single editable
fast-path total (a full rewrite of every stock-read across the app
to compute from the ledger is out of scope for what can be safely
verified without running the server), but every mutation now writes
a permanent, traceable ledger row alongside it, and the ledger can be
reconciled against current_stock at any time.

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "stock_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False, index=True),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_type", sa.String(20), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stock_ledger_entries")
