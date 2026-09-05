"""Add related_issue_id to stock_adjustments - lets a "material
returned unused" adjustment trace back to the specific Issue it's a
return against, a genuinely distinct concept from a generic
correction (matching the brief's explicit "material issues" and
"returns" as separate line items).

related_issue_id has an inline ForeignKey to issues.id - SQLite
cannot add a column with a constraint via a plain ALTER TABLE, so
this needs batch_alter_table with a naming convention (same reasoning
as migrations 0004/0012/0016/0018/0026/0044). migration_guards'
add_column_if_missing issues a plain op.add_column, which is only
safe for a column with no constraint - not sufficient here.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import column_exists, index_exists

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, "stock_adjustments", "related_issue_id"):
        if not index_exists(bind, "stock_adjustments", "ix_stock_adjustments_related_issue_id"):
            op.create_index("ix_stock_adjustments_related_issue_id", "stock_adjustments", ["related_issue_id"])
        return
    with op.batch_alter_table("stock_adjustments", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column(
            "related_issue_id", sa.Integer(),
            sa.ForeignKey("issues.id", name="fk_stock_adjustments_related_issue_id_issues"),
            nullable=True,
        ))
        batch_op.create_index("ix_stock_adjustments_related_issue_id", ["related_issue_id"])


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("stock_adjustments", naming_convention=NAMING_CONVENTION) as batch_op:
        if index_exists(bind, "stock_adjustments", "ix_stock_adjustments_related_issue_id"):
            batch_op.drop_index("ix_stock_adjustments_related_issue_id")
        if column_exists(bind, "stock_adjustments", "related_issue_id"):
            batch_op.drop_column("related_issue_id")
