"""Enforce one authoritative attendance record per
employee per calendar day, enforced at the database level (the
application-level check added in app/api/routes/attendance.py alone
is vulnerable to two concurrent requests both passing that check
before either commits).

Before adding the unique index, any pre-existing duplicate
(employee_id, date) groups are resolved: the most recently updated
record in each group is kept as authoritative, the others are removed
- but never silently. Each removal is logged (employee_id, date,
which record id was kept, which were removed) so a real deployment
has a genuine record of what this migration changed, matching "do not
blindly delete existing historical records - preserve the
authoritative record according to existing business semantics."

date is compared via its literal stored value (not a calendar-day
expression) since the application always stores midnight for this
column in practice (confirmed by reading the actual frontend
submission code) - the unique index matches that real-world usage
directly rather than a more complex, dialect-specific date()
expression.

Revision ID: 0060
Revises: 0059
Create Date: 2026-08-28
"""
import logging
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import create_index_if_missing, table_exists

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration.0060")


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "attendance"):
        return

    duplicate_groups = bind.execute(sa.text(
        "SELECT employee_id, date, COUNT(*) as cnt FROM attendance "
        "GROUP BY employee_id, date HAVING COUNT(*) > 1"
    )).fetchall()

    for employee_id, date_value, _count in duplicate_groups:
        rows = bind.execute(
            sa.text(
                "SELECT id FROM attendance WHERE employee_id = :eid AND date = :d "
                "ORDER BY updated_at DESC"
            ),
            {"eid": employee_id, "d": date_value},
        ).fetchall()
        row_ids = [r[0] for r in rows]
        keep_id, remove_ids = row_ids[0], row_ids[1:]
        logger.warning(
            "Duplicate attendance resolved for employee_id=%s date=%s: "
            "kept record #%s (most recently updated), removed %s",
            employee_id, date_value, keep_id, remove_ids,
        )
        for remove_id in remove_ids:
            bind.execute(sa.text("DELETE FROM attendance WHERE id = :rid"), {"rid": remove_id})

    create_index_if_missing(
        bind, "ix_attendance_employee_date_unique", "attendance",
        ["employee_id", "date"], unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_attendance_employee_date_unique", table_name="attendance")
