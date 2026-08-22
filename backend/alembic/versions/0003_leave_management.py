"""Add leaves table for Leave Management (PL/CL/SL).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "leaves",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("leave_type", sa.String(20), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("days", sa.Numeric(4, 1), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending", index=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("leaves")
