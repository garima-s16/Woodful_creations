"""Add Employee payroll/statutory fields (pan, uan, bank_name,
bank_account_number, tax_regime) - needed for salary slip generation.
Simple ADD COLUMN, no inline FK, so no batch_alter_table needed.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("pan", sa.String(10), nullable=True))
    op.add_column("employees", sa.Column("uan", sa.String(20), nullable=True))
    op.add_column("employees", sa.Column("bank_name", sa.String(100), nullable=True))
    op.add_column("employees", sa.Column("bank_account_number", sa.String(30), nullable=True))
    op.add_column("employees", sa.Column("tax_regime", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("tax_regime")
        batch_op.drop_column("bank_account_number")
        batch_op.drop_column("bank_name")
        batch_op.drop_column("uan")
        batch_op.drop_column("pan")
