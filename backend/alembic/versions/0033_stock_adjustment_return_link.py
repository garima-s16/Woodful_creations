"""Add related_issue_id to stock_adjustments - lets a "material
returned unused" adjustment trace back to the specific Issue it's a
return against, a genuinely distinct concept from a generic
correction (matching the brief's explicit "material issues" and
"returns" as separate line items).

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A plain op.add_column with an inline ForeignKey needs SQLite to add
    # a constraint via ALTER TABLE - unsupported outside batch mode ("No
    # support for ALTER of constraints in SQLite dialect"). create_index
    # itself is a plain CREATE INDEX, not an ALTER TABLE, so it stays
    # outside the batch block.
    with op.batch_alter_table("stock_adjustments") as batch_op:
        batch_op.add_column(sa.Column("related_issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=True))
    op.create_index("ix_stock_adjustments_related_issue_id", "stock_adjustments", ["related_issue_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_adjustments_related_issue_id", table_name="stock_adjustments")
    # Dropping a column that carries a FOREIGN KEY constraint hits the
    # same SQLite limitation in reverse - also needs batch mode.
    with op.batch_alter_table("stock_adjustments") as batch_op:
        batch_op.drop_column("related_issue_id")
