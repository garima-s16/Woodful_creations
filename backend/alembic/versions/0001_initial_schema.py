"""Initial schema - generated from the current SQLAlchemy models

This is the single source of truth for the database schema going forward.
database/schema.sql has been removed - it had drifted from these models
(e.g. inventory vs products, hashed_password vs password_hash) and is no
longer used anywhere.

Revision ID: 0001
Revises:
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profile_picture", sa.String(500), nullable=True),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("otp_secret", sa.String(255), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("phone", sa.String(20), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("lead_source", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1"),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "client_projects",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("client_id", sa.Integer(), index=True),
        sa.Column("project_name", sa.String(), index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("design_status", sa.String(), server_default="pending"),
        sa.Column("execution_status", sa.String(), server_default="pending"),
        sa.Column("delivery_status", sa.String(), server_default="pending"),
        sa.Column("estimated_delivery", sa.DateTime(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), server_default="0"),
        sa.Column("amount_paid", sa.Numeric(12, 2), server_default="0"),
        sa.Column("amount_pending", sa.Numeric(12, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("material_type", sa.String(), index=True),
        sa.Column("thickness", sa.Float(), index=True),
        sa.Column("category", sa.String(), index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="0"),
        sa.Column("min_quantity", sa.Integer(), server_default="10"),
        sa.Column("price_per_unit", sa.Numeric(12, 2), server_default="0"),
        sa.Column("unit", sa.String(), server_default="sheets"),
        sa.Column("sku", sa.String(), unique=True, nullable=True),
        sa.Column("supplier", sa.String(), nullable=True),
        sa.Column("last_restocked", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("client_id", sa.Integer(), index=True),
        sa.Column("client_name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("material_cost", sa.Numeric(12, 2), server_default="0"),
        sa.Column("labor_cost", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 2), server_default="0"),
        sa.Column("status", sa.String(), server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("employee_id", sa.Integer(), index=True),
        sa.Column("attendance_date", sa.DateTime(), index=True),
        sa.Column("check_in", sa.DateTime(), nullable=True),
        sa.Column("check_out", sa.DateTime(), nullable=True),
        sa.Column("hours_worked", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(), server_default="present"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), index=True),
        sa.Column("email", sa.String(), unique=True, index=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("salary", sa.Numeric(12, 2), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), index=True),
        sa.Column("email", sa.String(), unique=True, index=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("experience", sa.String(), nullable=True),
        sa.Column("resume_url", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="applied"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("candidate_id", sa.Integer(), index=True),
        sa.Column("round", sa.String(), nullable=True),
        sa.Column("scheduled_date", sa.DateTime(), index=True),
        sa.Column("interviewer", sa.String(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "salary_slips",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("employee_id", sa.Integer(), index=True),
        sa.Column("month", sa.String(), nullable=True),
        sa.Column("year", sa.String(), nullable=True),
        sa.Column("basic_salary", sa.Numeric(12, 2), server_default="0"),
        sa.Column("allowances", sa.Numeric(12, 2), server_default="0"),
        sa.Column("deductions", sa.Numeric(12, 2), server_default="0"),
        sa.Column("net_salary", sa.Numeric(12, 2), server_default="0"),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("client_project_id", sa.Integer(), sa.ForeignKey("client_projects.id"), nullable=True, index=True),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("payment_mode", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True, index=True),
        sa.Column("received_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_timestamps(),
    )

    for table_name, name_len in [
        ("project_statuses", 50),
        ("priorities", 50),
        ("payment_modes", 50),
        ("lead_sources", 50),
        ("project_types", 100),
        ("expense_categories", 100),
    ]:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(name_len), unique=True, nullable=False, index=True),
            sa.Column("description", sa.String(255), nullable=True),
            *([sa.Column("display_order", sa.Integer(), server_default="0")] if table_name == "project_statuses" else []),
            *_timestamps(),
        )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("module_name", sa.String(100), nullable=False, index=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.String(), index=True),
        sa.Column("action", sa.String(), index=True),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), index=True),
    )


def downgrade() -> None:
    for table in [
        "activity_logs", "audit_logs", "expense_categories", "project_types",
        "lead_sources", "payment_modes", "priorities", "project_statuses",
        "payments", "salary_slips", "interviews", "candidates", "employees",
        "attendance", "estimates", "products", "client_projects", "clients", "users",
    ]:
        op.drop_table(table)
