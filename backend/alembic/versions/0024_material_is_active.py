"""Add Material.is_active - default True so every existing material
stays exactly as visible/usable as before. Simple ADD COLUMN, no inline
FK - the SQLite batch_alter_table pattern from earlier migrations was
specifically for FK constraints, not needed here.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("materials") as batch_op:
        batch_op.drop_column("is_active")
