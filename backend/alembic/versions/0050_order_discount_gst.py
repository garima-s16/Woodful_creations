"""Add discount/tax_percent/tax_amount to orders (a critical
test gap: Order had no way to apply discount or GST at all -
order_value was just a raw sum of line items). Existing rows get
discount=0, tax_percent=18 (matching Estimate's own default), tax_amount
computed from their current order_value so existing data isn't
silently reinterpreted - see the data migration below.

Revision ID: 0050
Revises: 0049
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import column_exists

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, "orders", "discount"):
        return
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default="18"))
        batch_op.add_column(sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    # Existing orders keep their current order_value unchanged (it's
    # still the authoritative grand total) - tax_amount/discount simply
    # start at 0/0 for pre-existing rows, since there's no way to
    # retroactively know what portion of a historical order_value was
    # "tax" versus "price". Only new orders and edits going forward
    # compute these fields properly via app/modules/sales/calculations.py.


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("tax_amount")
        batch_op.drop_column("tax_percent")
        batch_op.drop_column("discount")
