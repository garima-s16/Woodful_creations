"""A new table for P0.3.3/3.4 - individual manufacturing
operations within a production job (Cutting -> CNC -> Assembly etc.),
with a single optional predecessor for a deliberately simple, linear
dependency model, not a general workflow engine.

A genuinely new table, not an addition to any existing one -
create_table_if_missing is idempotent, matching the established
pattern from 0059_chat_learning_candidates.py / 0065_report_history.py.

Revision ID: 0068
Revises: 0067
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "production_operations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("production_job_id", sa.Integer(), sa.ForeignKey("production_jobs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("operation_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource", sa.String(100), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Not Started"),
        sa.Column("depends_on_operation_id", sa.Integer(), sa.ForeignKey("production_operations.id"), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
    )
    create_index_if_missing(bind, "ix_production_operations_business_id", "production_operations", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_production_operations_production_job_id", "production_operations", ["production_job_id"])
    create_index_if_missing(bind, "ix_production_operations_status", "production_operations", ["status"])
    create_index_if_missing(bind, "ix_production_operations_employee_id", "production_operations", ["employee_id"])


def downgrade() -> None:
    op.drop_index("ix_production_operations_employee_id", table_name="production_operations")
    op.drop_index("ix_production_operations_status", table_name="production_operations")
    op.drop_index("ix_production_operations_production_job_id", table_name="production_operations")
    op.drop_index("ix_production_operations_business_id", table_name="production_operations")
    op.drop_table("production_operations")
