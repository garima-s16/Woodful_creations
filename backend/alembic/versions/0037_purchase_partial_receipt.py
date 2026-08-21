"""Add quantity_received to purchases - genuine gap against Family
6's explicit "partial receipts" task item. Backfills existing rows:
already-Received purchases get quantity_received = quantity (fully
received, matching their existing state); Ordered purchases get 0
(nothing received yet).

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = {c["name"] for c in sa.inspect(conn).get_columns("purchases")}
    if "quantity_received" not in existing_columns:
        op.add_column("purchases", sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False, server_default="0"))
    # Runs unconditionally, even if the column already existed (e.g. a
    # legacy database whose tables were created via create_all() against
    # already-current models) - otherwise already-Received purchases would
    # be silently left at quantity_received=0 forever. Idempotent: re-running
    # it just re-asserts quantity_received = quantity for Received rows.
    conn.execute(sa.text(
        "UPDATE purchases SET quantity_received = quantity WHERE receipt_status = 'Received'"
    ))


def downgrade() -> None:
    op.drop_column("purchases", "quantity_received")
