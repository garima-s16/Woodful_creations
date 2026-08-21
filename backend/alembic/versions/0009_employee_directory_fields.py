"""Add designation, email, manager to Employee - required by the Employee
Directory (P5) but not previously stored anywhere on this model.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("designation", sa.String(100), nullable=True))
    op.add_column("employees", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("manager", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("employees", "manager")
    op.drop_column("employees", "email")
    op.drop_column("employees", "designation")
