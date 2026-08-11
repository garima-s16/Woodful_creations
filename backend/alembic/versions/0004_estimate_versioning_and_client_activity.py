"""Add estimate versioning (version, parent_estimate_id) and the
client_activities table (client communication/interaction log).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estimates", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("estimates", sa.Column("parent_estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=True))
    op.create_index("ix_estimates_parent_estimate_id", "estimates", ["parent_estimate_id"])

    op.create_table(
        "client_activities",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("activity_type", sa.String(30), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("logged_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("client_activities")
    op.drop_index("ix_estimates_parent_estimate_id", table_name="estimates")
    op.drop_column("estimates", "parent_estimate_id")
    op.drop_column("estimates", "version")
