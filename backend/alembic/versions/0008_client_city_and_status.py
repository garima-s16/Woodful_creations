"""Add city and status to Client - both genuinely new fields (not derivable
from existing columns: address is a free-text block, not a structured
city/state/pincode breakdown, and there is no existing active/inactive
concept on Client), needed by the Client Register export.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import add_column_if_missing

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "clients", sa.Column("city", sa.String(100), nullable=True))
    add_column_if_missing(bind, "clients", sa.Column("status", sa.String(20), nullable=False, server_default="Active"))


def downgrade() -> None:
    op.drop_column("clients", "status")
    op.drop_column("clients", "city")
