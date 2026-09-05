"""Add client_type, state, pincode to Client - finalizes
the Client Excel/UI structure and requires Client Type (Individual/Business)
as a mandatory field, plus State and Pincode alongside the existing City.
client_type backfills existing rows to "Individual" (the more common case
for historical Woodful data) rather than leaving it null, since the column
is NOT NULL going forward - same backfill-then-constrain pattern as 0007.

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "clients", sa.Column("client_type", sa.String(20), nullable=True))
    bind.execute(sa.text("UPDATE clients SET client_type = 'Individual' WHERE client_type IS NULL"))
    # op.alter_column(nullable=False) alone
    # is not supported on SQLite (no native ALTER COLUMN); a fresh
    # SQLite database fails here without batch mode. batch_alter_table
    # is the standard Alembic mechanism for this - on SQLite it
    # recreates the table under the hood; on PostgreSQL/Neon it is a
    # transparent passthrough to the same plain ALTER this always ran
    # as, so production behavior is unchanged.
    with op.batch_alter_table("clients") as batch_op:
        batch_op.alter_column("client_type", existing_type=sa.String(20), nullable=False, server_default="Individual")
    add_column_if_missing(bind, "clients", sa.Column("state", sa.String(100), nullable=True))
    add_column_if_missing(bind, "clients", sa.Column("pincode", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "pincode")
    op.drop_column("clients", "state")
    op.drop_column("clients", "client_type")
