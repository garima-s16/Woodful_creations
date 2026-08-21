"""Add a proper address column to suppliers and employees, so the
permanent Woodful roster address can be displayed in the Supplier/
Employee UI directly instead of being packed into remarks.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.add_column(sa.Column("address", sa.Text(), nullable=True))

    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("address")

    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.drop_column("address")
