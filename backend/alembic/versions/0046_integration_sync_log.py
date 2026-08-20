"""Add integration_sync_logs - Family 19's Zoho/SAP integration
architecture. Append-only audit trail of every sync attempt; no
credentials table (those live in environment configuration only, per
Family 19's explicit "never expose external credentials" requirement -
there is nothing to store in the database at all).

Revision ID: 0046
Revises: 0045
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("external_system", sa.String(10), nullable=False, index=True),
        sa.Column("entity_type", sa.String(30), nullable=False, index=True),
        sa.Column("entity_id", sa.Integer(), nullable=False, index=True),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("dedup_key", sa.String(150), nullable=True, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_integration_sync_logs_entity", "integration_sync_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_sync_logs_entity", table_name="integration_sync_logs")
    op.drop_table("integration_sync_logs")
