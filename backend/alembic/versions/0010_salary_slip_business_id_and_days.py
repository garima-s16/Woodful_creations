"""Add business_id (SalarySlip was missed by 0005/0006 despite being a
user-facing business document like Payment/Order) plus working_days and
paid_days, which P9 requires on every salary slip but were never stored.

Self-contained backfill+NOT NULL for business_id (same generate_short_id
retry-on-collision pattern as migration 0007), since 0007 already ran and
only covered the tables it knew about at the time.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

from app.utils.id_generator import generate_short_id

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("salary_slips", sa.Column("business_id", sa.String(10), nullable=True))
    op.create_index("ix_salary_slips_business_id", "salary_slips", ["business_id"], unique=True)
    # Working days = calendar days in the period the employee was expected to
    # work; paid days = days actually paid for (may differ due to unpaid
    # leave). Both are plain editable numbers here for the same reason
    # PF/TDS are (see SalarySlip's model docstring) - the source-of-truth
    # attendance/leave reconciliation is a separate, larger payroll feature.
    op.add_column("salary_slips", sa.Column("working_days", sa.Numeric(5, 2), nullable=False, server_default="26"))
    op.add_column("salary_slips", sa.Column("paid_days", sa.Numeric(5, 2), nullable=False, server_default="26"))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM salary_slips WHERE business_id IS NULL")).fetchall()
    for (row_id,) in rows:
        for attempt in range(5):
            candidate_id = generate_short_id()
            try:
                with bind.begin_nested():
                    bind.execute(
                        sa.text("UPDATE salary_slips SET business_id = :bid WHERE id = :rid"),
                        {"bid": candidate_id, "rid": row_id},
                    )
                break
            except Exception:
                if attempt == 4:
                    raise
                continue

    with op.batch_alter_table("salary_slips") as batch_op:
        batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=False)


def downgrade() -> None:
    op.drop_column("salary_slips", "paid_days")
    op.drop_column("salary_slips", "working_days")
    with op.batch_alter_table("salary_slips") as batch_op:
        batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=True)
    op.drop_index("ix_salary_slips_business_id", table_name="salary_slips")
    op.drop_column("salary_slips", "business_id")
