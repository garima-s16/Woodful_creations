"""Add milestones - a genuine gap against Family 4's explicit task
list, lightweight by design (name/target_date/completed_date/remarks
per order), distinct from Order.project_status which already tracks
the detailed 11-stage production phase.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "milestones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.String(10), unique=True, index=True, nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=True),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("milestones")
