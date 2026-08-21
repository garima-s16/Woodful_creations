"""Add working_calendar_weekdays and company_holidays - lets working
days per month be computed dynamically instead of a hardcoded 26,
per the explicit "do not hard-code 26 working days" requirement.
Seeds the default weekday config (Mon-Sat working, Sunday off) so the
system has a sane default from the moment this migration runs,
without requiring a manual configuration step first.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "working_calendar_weekdays" not in existing_tables:
        op.create_table(
            "working_calendar_weekdays",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("weekday", sa.String(10), nullable=False, unique=True),
            sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "company_holidays" not in existing_tables:
        op.create_table(
            "company_holidays",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("date", sa.Date(), nullable=False, unique=True, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    weekdays_table = sa.table(
        "working_calendar_weekdays",
        sa.column("weekday", sa.String), sa.column("is_working", sa.Boolean),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    # Re-inspect rather than trust the pre-create_all() snapshot above -
    # the table may have just been created in this same call, or may
    # already hold real data from an earlier run of this migration
    # (or from create_all() + a prior partial migration attempt). Either
    # way, only seed the defaults if the table is genuinely empty, so
    # this is safe to run against a table that already has this data -
    # or, in principle, different data someone has since customized.
    existing_row_count = bind.execute(sa.text("SELECT COUNT(*) FROM working_calendar_weekdays")).scalar()
    if existing_row_count == 0:
        now = datetime.utcnow()
        default_rows = [
            {"weekday": "Monday", "is_working": True},
            {"weekday": "Tuesday", "is_working": True},
            {"weekday": "Wednesday", "is_working": True},
            {"weekday": "Thursday", "is_working": True},
            {"weekday": "Friday", "is_working": True},
            {"weekday": "Saturday", "is_working": True},
            {"weekday": "Sunday", "is_working": False},
        ]
        for row in default_rows:
            row["created_at"] = now
            row["updated_at"] = now
        op.bulk_insert(weekdays_table, default_rows)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    if "company_holidays" in existing_tables:
        op.drop_table("company_holidays")
    if "working_calendar_weekdays" in existing_tables:
        op.drop_table("working_calendar_weekdays")
