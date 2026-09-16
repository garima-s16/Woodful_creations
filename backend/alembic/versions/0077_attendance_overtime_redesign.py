"""Attendance & Overtime Command Center redesign.

Adds:
  - overtime_requests - see app.modules.hr.models.OvertimeRequest for
    the full design rationale (Draft -> Submitted -> Approved/Rejected
    workflow, separate from and converging with the existing bulk
    "Manage Overtime" action on the same Attendance.overtime_hours
    column via hr/services.py's apply_overtime_hours()).

No changes to the Attendance table itself - Scheduled/Payable hours
are computed from its existing standard_hours/attendance_status/
overtime_hours columns (see hr/services.py's attendance_period_summary
and its own docstring for the exact formula), not new columns.

Idempotent, using this project's existing shared migration guards
(create_table_if_missing/create_index_if_missing in
app.platform.database), matching 0073-0076's established convention.

Forward-only for the same reason as 0074-0076: purely additive, no
prior state to revert to.
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_table_if_missing, create_index_if_missing


revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_missing(
        bind, "overtime_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("requested_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approval_date", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_index_if_missing(bind, "ux_overtime_requests_business_id", "overtime_requests", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_overtime_requests_employee_id", "overtime_requests", ["employee_id"])
    create_index_if_missing(bind, "ix_overtime_requests_date", "overtime_requests", ["date"])
    create_index_if_missing(bind, "ix_overtime_requests_status", "overtime_requests", ["status"])


def downgrade() -> None:
    """Forward-only - see module docstring."""
    raise NotImplementedError(
        "Migration 0077 is forward-only. See this module's docstring for why a "
        "blind downgrade here would risk dropping data it did not create."
    )
