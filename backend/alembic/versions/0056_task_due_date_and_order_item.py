"""Add due_date/due_date_overridden/order_item_id to
DailyTask. due_date is the deadline for the work (distinct from `date`,
which is when the task is planned/assigned); due_date_overridden tracks
whether a Master has set a task-specific deadline so a later change to
the parent Order's delivery_date only propagates to tasks that were
never explicitly overridden. order_item_id is an optional link to the
specific Order Item/Product a task concerns - reuses the existing
OrderItem relationship rather than duplicating client/order/product
data onto DailyTask.

Revision ID: 0056
Revises: 0055
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing, create_index_if_missing

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "daily_tasks", sa.Column("due_date", sa.DateTime(), nullable=True))
    add_column_if_missing(
        bind, "daily_tasks",
        sa.Column("due_date_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_column_if_missing(bind, "daily_tasks", sa.Column("order_item_id", sa.Integer(), nullable=True))
    create_index_if_missing(bind, "ix_daily_tasks_due_date", "daily_tasks", ["due_date"])
    create_index_if_missing(bind, "ix_daily_tasks_order_item_id", "daily_tasks", ["order_item_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_tasks_order_item_id", table_name="daily_tasks")
    op.drop_index("ix_daily_tasks_due_date", table_name="daily_tasks")
    op.drop_column("daily_tasks", "order_item_id")
    op.drop_column("daily_tasks", "due_date_overridden")
    op.drop_column("daily_tasks", "due_date")
