"""Enforce, at the database level, that no two cash payments ever share
the same generated reference number.

OrderService._generate_cash_reference already checks for an existing
row with the candidate reference before inserting, but that
check-then-insert is not atomic: two concurrent cash payments can both
read the same "not taken yet" state and then both insert the same
CASH-YYYYMMDD-NNN value, since payments.reference_number previously had
no uniqueness constraint at all.

A blanket unique constraint on reference_number would be wrong - two
non-cash payments (bank transfer, cheque, UPI) could legitimately share
or coincidentally repeat a reference value that isn't ours to control.
Only the system-generated cash references need to be guaranteed unique,
and every one of those (and only those) is recognizable by its fixed
"CASH-" prefix - so this is a partial/filtered unique index, not a
table-wide constraint.

Before adding the index, any pre-existing duplicate cash references are
resolved by appending a disambiguating suffix to all but the first
occurrence in each duplicate group, so the migration never fails on
existing data and no historical payment is deleted or misattributed to
a different amount/order.

Revision ID: 0062
Revises: 0061
Create Date: 2026-08-29
"""
import logging
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import index_exists, table_exists

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

INDEX_NAME = "ux_payments_cash_reference_number"
logger = logging.getLogger("alembic.migration.0062")


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "payments"):
        return

    duplicate_groups = bind.execute(sa.text(
        "SELECT reference_number, COUNT(*) as cnt FROM payments "
        "WHERE reference_number LIKE 'CASH-%' "
        "GROUP BY reference_number HAVING COUNT(*) > 1"
    )).fetchall()
    for reference_number, _count in duplicate_groups:
        rows = bind.execute(
            sa.text("SELECT id FROM payments WHERE reference_number = :ref ORDER BY id"),
            {"ref": reference_number},
        ).fetchall()
        row_ids = [r[0] for r in rows]
        for suffix, dup_id in enumerate(row_ids[1:], start=1):
            new_ref = f"{reference_number}-DUP{suffix}"
            logger.warning(
                "Duplicate cash payment reference resolved: payment #%s reference_number "
                "changed from %s to %s (original amount/order untouched)",
                dup_id, reference_number, new_ref,
            )
            bind.execute(
                sa.text("UPDATE payments SET reference_number = :new_ref WHERE id = :pid"),
                {"new_ref": new_ref, "pid": dup_id},
            )

    if not index_exists(bind, "payments", INDEX_NAME):
        op.create_index(
            INDEX_NAME, "payments", ["reference_number"], unique=True,
            postgresql_where=sa.text("reference_number LIKE 'CASH-%'"),
            sqlite_where=sa.text("reference_number LIKE 'CASH-%'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "payments", INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="payments")
