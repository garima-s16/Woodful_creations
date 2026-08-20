"""Add AutomationLog - Family 13's traceable audit trail for
automation-generated actions (what triggered it, when, what action
occurred, whether it succeeded, the related business record).

Fresh CREATE TABLE, same shape as 0019's notifications table (one
generic related_entity_type/related_entity_id pair, following the
established pattern rather than a dedicated column per entity type).

Revision ID: 0045
Revises: 0044
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rule_key", sa.String(50), nullable=False),
        sa.Column("trigger_event", sa.String(50), nullable=False),
        sa.Column("condition_summary", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("related_entity_type", sa.String(30), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id"), nullable=True),
        sa.Column("dedup_key", sa.String(150), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_automation_logs_rule_key", "automation_logs", ["rule_key"])
    op.create_index("ix_automation_logs_status", "automation_logs", ["status"])
    op.create_index("ix_automation_logs_dedup_key", "automation_logs", ["dedup_key"])


def downgrade() -> None:
    op.drop_index("ix_automation_logs_dedup_key", table_name="automation_logs")
    op.drop_index("ix_automation_logs_status", table_name="automation_logs")
    op.drop_index("ix_automation_logs_rule_key", table_name="automation_logs")
    op.drop_table("automation_logs")
