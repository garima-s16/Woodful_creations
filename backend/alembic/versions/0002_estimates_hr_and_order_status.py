"""Add Estimates, Candidates, Interviews, Salary Slips, and fine-grained
Order status tracking (design/execution/delivery status alongside the
overall project_status pipeline stage).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing, add_column_if_missing

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "orders", sa.Column("design_status", sa.String(50), nullable=False, server_default="Pending"))
    add_column_if_missing(bind, "orders", sa.Column("execution_status", sa.String(50), nullable=False, server_default="Pending"))
    add_column_if_missing(bind, "orders", sa.Column("delivery_status", sa.String(50), nullable=False, server_default="Pending"))

    create_table_if_missing(
        bind,
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("estimate_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("labor_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default="18"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("experience", sa.String(100), nullable=True),
        sa.Column("resume_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Applied", index=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False, index=True),
        sa.Column("round", sa.String(50), nullable=True),
        sa.Column("scheduled_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("interviewer", sa.String(255), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Scheduled", index=True),
    )

    create_table_if_missing(
        bind,
        "salary_slips",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("month", sa.String(20), nullable=False),
        sa.Column("year", sa.String(4), nullable=False),
        sa.Column("basic", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("da", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("hra", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("overtime_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pf_deduction", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tds_deduction", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_salary", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    )


def downgrade() -> None:
    op.drop_table("salary_slips")
    op.drop_table("interviews")
    op.drop_table("candidates")
    op.drop_table("estimates")
    op.drop_column("orders", "delivery_status")
    op.drop_column("orders", "execution_status")
    op.drop_column("orders", "design_status")
