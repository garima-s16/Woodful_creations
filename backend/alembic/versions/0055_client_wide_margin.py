"""Make client_product_rates.product_id nullable - a NULL product_id
represents a client-wide default margin (e.g. "Meenal gets 15% on
everything"), distinct from a specific-product override.

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("client_product_rates") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("client_product_rates") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
