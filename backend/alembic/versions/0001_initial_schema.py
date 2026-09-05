"""Initial schema - materials/procurement/orders domain, generated from the
current SQLAlchemy models (replaces the earlier CRM/HR-domain schema).

Revision ID: 0001
Revises:
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _base_cols():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _lookup_table(name):
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        name,
        *_base_cols(),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "users",
        *_base_cols(),
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
        sa.Column("cannot_be_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    for lookup in [
        "units", "material_categories", "stock_statuses", "stock_payment_statuses",
        "locations", "supplier_terms", "departments", "task_statuses",
        "attendance_statuses", "machines", "project_statuses", "priorities",
        "payment_modes", "lead_sources", "project_types", "expense_categories",
    ]:
        _lookup_table(lookup)

    create_table_if_missing(
        bind,
        "suppliers",
        *_base_cols(),
        sa.Column("supplier_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("contact_person", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("gstin", sa.String(20), nullable=True),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "materials",
        *_base_cols(),
        sa.Column("material_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("brand_grade", sa.String(100), nullable=True),
        sa.Column("thickness_size", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("opening_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_purchased", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_issued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stock", sa.Integer(), nullable=False, server_default="0", index=True),
        sa.Column("minimum_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True, index=True),
        sa.Column("location", sa.String(100), nullable=True),
    )

    create_table_if_missing(
        bind,
        "clients",
        *_base_cols(),
        sa.Column("client_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("phone", sa.String(20), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lead_source", sa.String(100), nullable=True),
        sa.Column("first_contact_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "orders",
        *_base_cols(),
        sa.Column("order_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("project_type", sa.String(100), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("delivery_date", sa.DateTime(), nullable=True),
        sa.Column("order_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("advance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_received", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_received", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("project_status", sa.String(50), nullable=False, server_default="Enquiry", index=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("supervisor", sa.String(255), nullable=True),
        sa.Column("site_address", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "employees",
        *_base_cols(),
        sa.Column("employee_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("department", sa.String(100), nullable=True, index=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("joining_date", sa.DateTime(), nullable=True),
        sa.Column("monthly_salary", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("emergency_contact", sa.String(20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "purchases",
        *_base_cols(),
        sa.Column("purchase_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("gst_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("gst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("invoice_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="Paid"),
    )

    create_table_if_missing(
        bind,
        "issues",
        *_base_cols(),
        sa.Column("issue_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False, index=True),
        sa.Column("quantity_issued", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("issued_to", sa.String(255), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "payments",
        *_base_cols(),
        sa.Column("receipt_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("payment_mode", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("received_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "project_expenses",
        *_base_cols(),
        sa.Column("expense_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("paid_to", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "attendance",
        *_base_cols(),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("in_time", sa.DateTime(), nullable=True),
        sa.Column("out_time", sa.DateTime(), nullable=True),
        sa.Column("standard_hours", sa.Numeric(5, 2), nullable=False, server_default="8"),
        sa.Column("attendance_status", sa.String(20), nullable=False, server_default="Present"),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "daily_tasks",
        *_base_cols(),
        sa.Column("task_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True, index=True),
        sa.Column("task_description", sa.String(500), nullable=False),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("planned_start", sa.Time(), nullable=True),
        sa.Column("planned_end", sa.Time(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Not Started", index=True),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_by", sa.String(255), nullable=True),
        sa.Column("delay_reason", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
        "production_jobs",
        *_base_cols(),
        sa.Column("job_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("machine", sa.String(100), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True, index=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True, index=True),
        sa.Column("operation", sa.String(255), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True, index=True),
        sa.Column("planned_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Not Started", index=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )

    create_table_if_missing(
        bind,
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


def downgrade() -> None:
    for table in [
        "audit_logs", "production_jobs", "daily_tasks", "attendance",
        "project_expenses", "payments", "issues", "purchases", "employees",
        "orders", "clients", "materials", "suppliers",
        "expense_categories", "project_types", "lead_sources", "payment_modes",
        "priorities", "project_statuses", "machines", "attendance_statuses",
        "task_statuses", "departments", "supplier_terms", "locations",
        "stock_payment_statuses", "stock_statuses", "material_categories", "units",
        "users",
    ]:
        op.drop_table(table)
