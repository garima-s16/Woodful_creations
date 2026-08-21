"""Normalize DailyTask.status to exactly TO DO / DOING / BLOCKED / DONE.
Data migration - maps existing rows rather than losing them:
Not Started -> TO DO, In Progress -> DOING, On Hold -> BLOCKED,
Completed -> DONE. Scoped to daily_tasks only - ProductionJob and
Order use separate status vocabularies and are untouched.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

MAPPING_UP = {
    "Not Started": "TO DO",
    "In Progress": "DOING",
    "On Hold": "BLOCKED",
    "Completed": "DONE",
}
MAPPING_DOWN = {v: k for k, v in MAPPING_UP.items()}


def upgrade() -> None:
    conn = op.get_bind()
    daily_tasks = sa.table("daily_tasks", sa.column("status", sa.String))
    for old, new in MAPPING_UP.items():
        conn.execute(daily_tasks.update().where(daily_tasks.c.status == old).values(status=new))


def downgrade() -> None:
    conn = op.get_bind()
    daily_tasks = sa.table("daily_tasks", sa.column("status", sa.String))
    for new, old in MAPPING_DOWN.items():
        conn.execute(daily_tasks.update().where(daily_tasks.c.status == new).values(status=old))
