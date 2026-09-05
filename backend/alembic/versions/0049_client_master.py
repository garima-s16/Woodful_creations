"""Client Master: add contact_person/site_address/
gstin (matching the real Woodful Client Master reference sheet's
columns), and make phone + business_id genuinely mandatory at the
database level, not just in the API schema.

Any pre-existing client row with a NULL phone is backfilled with a
clearly-marked placeholder ("0000000000") before the NOT NULL
constraint is applied - the same approach migration 0007 used for
business_id - rather than silently leaving legacy rows in a state the
new constraint would reject. A backfilled placeholder is easy to find
and correct (search for that exact value) rather than an invented
fake-but-plausible number.

Revision ID: 0049
Revises: 0048
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import column_exists

from app.platform.database.id_generator import generate_short_id

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

PLACEHOLDER_PHONE = "0000000000"


def upgrade() -> None:
    bind = op.get_bind()

    if not all(column_exists(bind, "clients", c) for c in
               ("contact_person", "alternate_phone", "site_address", "gstin")):
        with op.batch_alter_table("clients") as batch_op:
            if not column_exists(bind, "clients", "contact_person"):
                batch_op.add_column(sa.Column("contact_person", sa.String(255), nullable=True))
            if not column_exists(bind, "clients", "alternate_phone"):
                batch_op.add_column(sa.Column("alternate_phone", sa.String(20), nullable=True))
            if not column_exists(bind, "clients", "site_address"):
                batch_op.add_column(sa.Column("site_address", sa.Text(), nullable=True))
            if not column_exists(bind, "clients", "gstin"):
                batch_op.add_column(sa.Column("gstin", sa.String(20), nullable=True))

    bind.execute(
        sa.text("UPDATE clients SET phone = :placeholder WHERE phone IS NULL OR phone = ''"),
        {"placeholder": PLACEHOLDER_PHONE},
    )

    # Any row still missing business_id despite migration 0007 gets a
    # REAL, valid one - the same generator + retry-on-collision pattern
    # 0007 already uses for every other table, not client_code (which
    # is not a valid 10-char business_id shape - "CL-001" doesn't match
    # [A-Z0-9]{10} - and would just move the problem to the API layer
    # the first time that row was read back).
    rows = bind.execute(sa.text("SELECT id FROM clients WHERE business_id IS NULL")).fetchall()
    for (row_id,) in rows:
        for attempt in range(5):
            candidate_id = generate_short_id()
            try:
                with bind.begin_nested():
                    bind.execute(
                        sa.text("UPDATE clients SET business_id = :bid WHERE id = :rid"),
                        {"bid": candidate_id, "rid": row_id},
                    )
                break
            except Exception:
                if attempt == 4:
                    raise
                continue

    with op.batch_alter_table("clients") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(20), nullable=False)
        batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("clients") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(20), nullable=True)
        batch_op.alter_column("business_id", existing_type=sa.String(10), nullable=True)
        batch_op.drop_column("gstin")
        batch_op.drop_column("site_address")
        batch_op.drop_column("alternate_phone")
        batch_op.drop_column("contact_person")
