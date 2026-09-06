"""Family P0.44 - Salary Advance Management: a new salary_advances
table (the full request/approve/reject/recover workflow) and a new
advance_deduction column on salary_slips (defaults to 0, so every
existing slip is completely unaffected - the recovery action is the
only path that ever sets it to something else).

Revision ID: 0072
Revises: 0071
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing, add_column_if_missing

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "salary_advances",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("requested_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("request_date", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("approved_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approval_date", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("recovery_month", sa.String(20), nullable=True),
        sa.Column("recovery_year", sa.String(4), nullable=True),
        sa.Column("recovered_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_index_if_missing(bind, "ix_salary_advances_business_id", "salary_advances", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_salary_advances_employee_id", "salary_advances", ["employee_id"])

    add_column_if_missing(bind, "salary_slips", sa.Column("advance_deduction", sa.Numeric(12, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("salary_slips", "advance_deduction")
    op.drop_index("ix_salary_advances_employee_id", table_name="salary_advances")
    op.drop_index("ix_salary_advances_business_id", table_name="salary_advances")
    op.drop_table("salary_advances")
