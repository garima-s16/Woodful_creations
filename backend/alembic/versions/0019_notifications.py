"""Add Notification - real, event-driven notifications (low stock,
purchase received, overdue payment, ...), not fabricated demo rows.
Generic related_entity_type/related_entity_id pair rather than a
dedicated field per entity type, matching the same pattern already used
for ChatContext.

Fresh CREATE TABLE with one foreign key, natively supported since it's
a new table, not an ALTER on an existing one.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("notification_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("related_entity_type", sa.String(30), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("action_path", sa.String(255), nullable=True),
        sa.Column("dedup_key", sa.String(150), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_notifications_business_id"),
    )
    create_index_if_missing(bind, "ix_notifications_notification_type", "notifications", ["notification_type"])
    create_index_if_missing(bind, "ix_notifications_is_read", "notifications", ["is_read"])
    create_index_if_missing(bind, "ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    create_index_if_missing(bind, "ix_notifications_dedup_key", "notifications", ["dedup_key"])


def downgrade() -> None:
    op.drop_table("notifications")
