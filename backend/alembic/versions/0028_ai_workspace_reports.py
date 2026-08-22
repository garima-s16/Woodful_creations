"""Add ai_workspace_reports table - persisted multi-step AI analysis
results (e.g. "what's blocking this order"), a real viewable Woodful
artifact rather than a one-off chat response.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "ai_workspace_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_workspace_reports")
