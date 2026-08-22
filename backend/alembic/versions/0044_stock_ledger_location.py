"""Add location_id to stock_ledger_entries - true multi-location stock.

Material.location_id remains as the single "primary location" field for
backward compatibility (existing dashboards/PDF/chatbot reads keep working
unchanged). This migration only adds the column ledger entries need to
record WHERE a movement happened, so per-location balances can be derived
by summing quantity_delta grouped by location_id. No existing data is
touched - old ledger rows simply have location_id = NULL, and callers that
need a location for them fall back to the material's current location_id
at read time (see StockService.get_location_balances).

Revision ID: 0044
Revises: 0043
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_ledger_entries",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    op.create_index(
        "ix_stock_ledger_entries_location_id", "stock_ledger_entries", ["location_id"],
    )
    op.add_column(
        "purchases",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    op.create_index("ix_purchases_location_id", "purchases", ["location_id"])
    op.add_column(
        "issues",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    op.create_index("ix_issues_location_id", "issues", ["location_id"])
    op.add_column(
        "stock_adjustments",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    op.create_index("ix_stock_adjustments_location_id", "stock_adjustments", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_adjustments_location_id", table_name="stock_adjustments")
    op.drop_column("stock_adjustments", "location_id")
    op.drop_index("ix_issues_location_id", table_name="issues")
    op.drop_column("issues", "location_id")
    op.drop_index("ix_purchases_location_id", table_name="purchases")
    op.drop_column("purchases", "location_id")
    op.drop_index("ix_stock_ledger_entries_location_id", table_name="stock_ledger_entries")
    op.drop_column("stock_ledger_entries", "location_id")
