"""Add id_sequences - backs the centralized, incremental business_id
generator (Family 21). Replaces the previous random-generation scheme
(generate_short_id) for all new records going forward; existing
business_id values are untouched (the column is populated the same way
as before, just with values drawn from this new sequence instead of
random ones - both shapes satisfy the same [A-Z0-9]{10} contract, so no
backfill or reformatting of existing rows is needed).

This table has exactly one purpose: its autoincrement primary key is a
single, database-guaranteed monotonically-increasing counter shared by
every entity type, so business_ids stay ordered relative to each other
across the whole system, not just within one table.

Revision ID: 0047
Revises: 0046
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "id_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    )


def downgrade() -> None:
    op.drop_table("id_sequences")
