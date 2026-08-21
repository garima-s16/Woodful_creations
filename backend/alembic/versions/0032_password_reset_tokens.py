"""Add password_reset_tokens - the previously-identified gap: no
password recovery flow existed at all. Only a hash of the token is
ever stored.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Guarded the same way 0030/0031 already are: don't assume this
    # table can't already exist just because this is the migration that
    # normally creates it - a database can reach this point with the
    # table already physically present (created outside Alembic, a
    # restored backup, an interrupted prior upgrade, etc.), and blindly
    # calling create_table would then fail startup with "table already
    # exists" instead of just adopting what's already there.
    if "password_reset_tokens" not in inspector.get_table_names():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(64), nullable=False, index=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
