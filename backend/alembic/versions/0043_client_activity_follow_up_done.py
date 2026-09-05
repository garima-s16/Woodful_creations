"""Add follow_up_done to client_activities.

CRM gap: follow_up_date was already captured on activities,
but there was no way to ever mark a follow-up as handled, and nothing
outside the chatbot's ad-hoc suggestion list surfaced them. Without a
done flag, a resolved follow-up (e.g. "call back next week") would
stay in every future "pending follow-ups" query forever. This adds
the missing state so a real pending-follow-ups list can exclude
completed ones.

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, 
        "client_activities",
        sa.Column("follow_up_done", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("client_activities", "follow_up_done")
