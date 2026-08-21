"""Client Master (Family 21 section): add contact_person/site_address/
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

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

PLACEHOLDER_PHONE = "0000000000"


def upgrade() -> None:
    bind = op.get_bind()
    # Guard each column individually - and, crucially, run the backfill
    # and NOT NULL enforcement below unconditionally regardless - so a
    # legacy database whose "clients" table was created via create_all()
    # (already having some/all of these columns) still gets its phone/
    # business_id backfilled and enforced, rather than silently skipping
    # that as part of one failed batch of column adds.
    existing_columns = {c["name"] for c in sa.inspect(bind).get_columns("clients")}
    with op.batch_alter_table("clients") as batch_op:
        if "contact_person" not in existing_columns:
            batch_op.add_column(sa.Column("contact_person", sa.String(255), nullable=True))
        if "alternate_phone" not in existing_columns:
            batch_op.add_column(sa.Column("alternate_phone", sa.String(20), nullable=True))
        if "site_address" not in existing_columns:
            batch_op.add_column(sa.Column("site_address", sa.Text(), nullable=True))
        if "gstin" not in existing_columns:
            batch_op.add_column(sa.Column("gstin", sa.String(20), nullable=True))

    bind.execute(
        sa.text("UPDATE clients SET phone = :placeholder WHERE phone IS NULL OR phone = ''"),
        {"placeholder": PLACEHOLDER_PHONE},
    )
    bind.execute(sa.text("UPDATE clients SET business_id = client_code WHERE business_id IS NULL"))
    # The line above is a last-resort fallback only reached if some row
    # still has no business_id despite migration 0007 - client_code is
    # not a valid 10-char business_id shape, but it's better than a
    # NOT NULL migration failing outright; such a row would be visibly
    # wrong (not [A-Z0-9]{10}) and easy to spot for manual correction.

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
