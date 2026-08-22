"""Add blocker_reason to production_jobs - genuine gap against
Family 7's explicit "blockers" task item. "Blocked" status itself
needs no schema change (status is a plain string), but there was no
dedicated reason field, matching DailyTask's existing
status="BLOCKED" + delay_reason pattern.

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import add_column_if_missing

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "production_jobs", sa.Column("blocker_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("production_jobs", "blocker_reason")
