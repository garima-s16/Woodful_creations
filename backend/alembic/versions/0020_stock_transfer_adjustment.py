"""Add StockTransfer and StockAdjustment - real, audited stock-movement
records (Sections 12/13 of an earlier brief), never previously built.
Both fresh CREATE TABLEs with FKs, natively supported since neither is
an ALTER on an existing table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "stock_transfers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("from_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("to_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("transferred_by", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_stock_transfers_business_id"),
    )
    create_index_if_missing(bind, "ix_stock_transfers_material_id", "stock_transfers", ["material_id"])

    create_table_if_missing(
        bind,
        "stock_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("adjustment_type", sa.String(30), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("stock_before", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("adjusted_by", sa.String(100), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_stock_adjustments_business_id"),
    )
    create_index_if_missing(bind, "ix_stock_adjustments_material_id", "stock_adjustments", ["material_id"])


def downgrade() -> None:
    op.drop_table("stock_adjustments")
    op.drop_table("stock_transfers")
