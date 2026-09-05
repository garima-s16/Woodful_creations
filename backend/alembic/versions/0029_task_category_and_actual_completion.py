"""Add task_category and actual_completed_at to daily_tasks - two
genuine gaps against the workforce feature brief's field list
(task category, actual completion date/time).

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "daily_tasks", sa.Column("task_category", sa.String(50), nullable=True))
    add_column_if_missing(bind, "daily_tasks", sa.Column("actual_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_tasks", "actual_completed_at")
    op.drop_column("daily_tasks", "task_category")
