"""Family P0.43 - attendance.overtime_hours becomes a real column.
Previously this was a computed property (working_hours minus
standard_hours) - the corrected business rule is that overtime is a
fact the Master explicitly states, not derived from clock in/out
times, so it needs real storage. Defaults to 0 (an attendance record
with no stated overtime has none), so every existing row is
unaffected on upgrade.

Revision ID: 0073
Revises: 0072
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "attendance", sa.Column("overtime_hours", sa.Numeric(5, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("attendance", "overtime_hours")
