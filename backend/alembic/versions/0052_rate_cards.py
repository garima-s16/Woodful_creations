"""Add rate_cards - the three-layer Rate Master (Indore Market
Reference / Woodful Internal Cost / Woodful Selling Rate), versioned
so a rate change never mutates a historical Estimate/Order's already-
snapshotted rate.

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "rate_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rate_code", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("business_id", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("category", sa.String(100), nullable=False, index=True),
        sa.Column("subcategory", sa.String(100), nullable=True, index=True),
        sa.Column("item_name", sa.String(255), nullable=False, index=True),
        sa.Column("specification", sa.String(255), nullable=True),
        sa.Column("location", sa.String(100), nullable=False, server_default="Indore, Madhya Pradesh"),
        sa.Column("uom", sa.String(20), nullable=False),
        sa.Column("market_reference_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("woodful_cost_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("woodful_selling_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("overhead_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("target_margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("wastage_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=True, server_default="18"),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="NOT_VERIFIED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("rate_cards.id"), nullable=True),
        sa.Column("override_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("override_by", sa.String(255), nullable=True),
        sa.Column("override_at", sa.DateTime(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rate_cards")
