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
    # Adding a column with an inline ForeignKey via a plain op.add_column
    # requires SQLite to add a constraint via ALTER TABLE, which the
    # SQLite dialect explicitly does not support ("No support for ALTER
    # of constraints in SQLite dialect") - it needs batch mode (Alembic's
    # copy-new-table-and-swap strategy) instead. Index creation itself
    # is a plain CREATE INDEX, not an ALTER TABLE, so it's unaffected and
    # stays outside the batch block.
    with op.batch_alter_table("stock_ledger_entries") as batch_op:
        batch_op.add_column(sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index(
        "ix_stock_ledger_entries_location_id", "stock_ledger_entries", ["location_id"],
    )
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.add_column(sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index("ix_purchases_location_id", "purchases", ["location_id"])
    with op.batch_alter_table("issues") as batch_op:
        batch_op.add_column(sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index("ix_issues_location_id", "issues", ["location_id"])
    with op.batch_alter_table("stock_adjustments") as batch_op:
        batch_op.add_column(sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index("ix_stock_adjustments_location_id", "stock_adjustments", ["location_id"])


def downgrade() -> None:
    # Dropping a column that carries a FOREIGN KEY constraint hits the
    # same SQLite limitation in reverse - it also needs batch mode.
    op.drop_index("ix_stock_adjustments_location_id", table_name="stock_adjustments")
    with op.batch_alter_table("stock_adjustments") as batch_op:
        batch_op.drop_column("location_id")
    op.drop_index("ix_issues_location_id", table_name="issues")
    with op.batch_alter_table("issues") as batch_op:
        batch_op.drop_column("location_id")
    op.drop_index("ix_purchases_location_id", table_name="purchases")
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.drop_column("location_id")
    op.drop_index("ix_stock_ledger_entries_location_id", table_name="stock_ledger_entries")
    with op.batch_alter_table("stock_ledger_entries") as batch_op:
        batch_op.drop_column("location_id")
