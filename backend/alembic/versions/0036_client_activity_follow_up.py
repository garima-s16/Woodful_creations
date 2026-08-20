"""Add follow_up_date to client_activities - genuine gap, lets a
logged interaction carry a scheduled follow-up date, giving the AI
follow-up-suggestions capability real data to query rather than
invent.

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_activities", sa.Column("follow_up_date", sa.DateTime(), nullable=True))
    op.create_index("ix_client_activities_follow_up_date", "client_activities", ["follow_up_date"])


def downgrade() -> None:
    op.drop_index("ix_client_activities_follow_up_date", table_name="client_activities")
    op.drop_column("client_activities", "follow_up_date")
