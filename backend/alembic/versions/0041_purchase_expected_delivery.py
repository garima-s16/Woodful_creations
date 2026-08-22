"""Add expected_delivery_date to purchases - explicitly named in
Family 6's task list ("expected delivery"), needed to honestly
identify delayed deliveries rather than invent an arbitrary
threshold.

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import add_column_if_missing

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "purchases", sa.Column("expected_delivery_date", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("purchases", "expected_delivery_date")
