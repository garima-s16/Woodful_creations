"""Add DailyTask handoff/subtask fields (created_by, parent_task_id,
previous_task_id) and the new task_comments table. Self-referential FKs
need batch_alter_table for SQLite.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing, add_column_if_missing, column_exists

revision = "0026"
down_revision = "0025"
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
    bind = op.get_bind()
    add_column_if_missing(bind, "daily_tasks", sa.Column("created_by", sa.String(255), nullable=True))
    if not column_exists(bind, "daily_tasks", "parent_task_id"):
        with op.batch_alter_table("daily_tasks", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column(
                "parent_task_id", sa.Integer(),
                sa.ForeignKey("daily_tasks.id", name="fk_daily_tasks_parent_task_id_daily_tasks"), nullable=True,
            ))
            batch_op.add_column(sa.Column(
                "previous_task_id", sa.Integer(),
                sa.ForeignKey("daily_tasks.id", name="fk_daily_tasks_previous_task_id_daily_tasks"), nullable=True,
            ))
            batch_op.create_index("ix_daily_tasks_parent_task_id", ["parent_task_id"])
            batch_op.create_index("ix_daily_tasks_previous_task_id", ["previous_task_id"])

    create_table_if_missing(
        bind, "task_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("daily_tasks.id"), nullable=False, index=True),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("task_comments")
    with op.batch_alter_table("daily_tasks", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_daily_tasks_previous_task_id")
        batch_op.drop_index("ix_daily_tasks_parent_task_id")
        batch_op.drop_column("previous_task_id")
        batch_op.drop_column("parent_task_id")
    op.drop_column("daily_tasks", "created_by")
