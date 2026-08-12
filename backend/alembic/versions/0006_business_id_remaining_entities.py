"""Add business_id to the four user-facing entities migration 0005 missed:
Candidate, Interview, Leave, Attendance. Same pattern as 0005 - plain
nullable column + separate unique index, no inline constraint, so SQLite's
ALTER TABLE can add it directly without batch mode.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = ["candidates", "interviews", "leaves", "attendance"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("business_id", sa.String(10), nullable=True))
        op.create_index(f"ix_{table}_business_id", table, ["business_id"], unique=True)


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_business_id", table_name=table)
        op.drop_column(table, "business_id")
