"""Add users.password_changed_at, so an authentication session already
issued before a password reset stops being honored afterward.

Previously, get_current_user only decoded and trusted the JWT's own
signature/expiry - it never re-checked the account's current state. A
successful password reset (a genuine "I no longer trust whoever might
have had access to this account" signal from the user) had no effect
on any token issued before it: an old, stolen, or shared token kept
working right up until its normal expiry, regardless of the reset.

This column, once set, gives get_current_user something concrete to
compare a token's issued-at time against. NULL (the default, and the
value for every existing account until its first future reset) means
no invalidation point exists yet - no currently-valid session is
retroactively broken by adding this column.

Revision ID: 0063
Revises: 0062
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import add_column_if_missing, table_exists

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "users"):
        return
    add_column_if_missing(bind, "users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "users"):
        op.drop_column("users", "password_changed_at")
