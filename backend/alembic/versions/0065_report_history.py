"""A new table tracking report generation
metadata for the existing 15-day retention requirement. Records only
that a report was generated (report_type, report_date, generated_at,
storage_identity) - never any business data, and never any underlying
business record this app already has (tasks, orders, etc). Rows older
than 15 days are safe to expire, since they are history of a
generation event, not a business record in their own right.

A genuinely new table, not an addition to any existing one -
create_table_if_missing is idempotent, matching the established
pattern from 0059_chat_learning_candidates.py.

Revision ID: 0065
Revises: 0064
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "report_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("report_date", sa.DateTime(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("storage_identity", sa.String(255), nullable=True),
    )
    create_index_if_missing(bind, "ix_report_history_report_type", "report_history", ["report_type"])


def downgrade() -> None:
    op.drop_index("ix_report_history_report_type", table_name="report_history")
    op.drop_table("report_history")
