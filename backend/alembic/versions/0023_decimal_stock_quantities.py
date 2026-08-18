"""Change Material's stock-quantity columns (and StockTransfer/
StockAdjustment's quantity columns) from Integer to Numeric(12,2).

Purchase.quantity and Issue.quantity_issued were already correctly
Numeric - this migration fixes where that precision was getting
silently truncated: the moment a decimal quantity flowed into
Material's aggregate fields (current_stock, total_purchased, etc.) via
int(quantity) in the service layer. A material measured in kg/litres/
metres (e.g. 2.5 kg of adhesive) needs its stock numbers to actually
hold that precision, not round it away.

Uses batch_alter_table since SQLite cannot ALTER a column's type
directly - this rebuilds the table under the hood, the same pattern
used for the FK changes in earlier migrations (0004/0012).

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("opening_stock", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("total_purchased", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("total_issued", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("current_stock", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("minimum_stock", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)

    with op.batch_alter_table("stock_transfers", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("quantity", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)

    with op.batch_alter_table("stock_adjustments", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("quantity_delta", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("stock_before", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column("stock_after", type_=sa.Numeric(12, 2), existing_type=sa.Integer(), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("stock_adjustments", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("stock_after", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("stock_before", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("quantity_delta", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)

    with op.batch_alter_table("stock_transfers", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("quantity", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)

    with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.alter_column("minimum_stock", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("current_stock", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("total_issued", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("total_purchased", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
        batch_op.alter_column("opening_stock", type_=sa.Integer(), existing_type=sa.Numeric(12, 2), existing_nullable=False)
