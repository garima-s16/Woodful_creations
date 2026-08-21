"""Customer-specific pricing (client_product_rates), Estimate margin
override, and historical pricing-provenance snapshot fields on
estimate/order line items (is_custom_item, pricing_rule_applied,
applied_margin_percent).

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_product_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("fixed_selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("client_id", "product_id", name="uq_client_product_rate"),
    )

    with op.batch_alter_table("estimates") as batch_op:
        batch_op.add_column(sa.Column("margin_percent_override", sa.Numeric(5, 2), nullable=True))

    with op.batch_alter_table("estimate_line_items") as batch_op:
        batch_op.add_column(sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("pricing_rule_applied", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True))

    with op.batch_alter_table("order_items") as batch_op:
        batch_op.add_column(sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("pricing_rule_applied", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_column("applied_margin_percent")
        batch_op.drop_column("pricing_rule_applied")
        batch_op.drop_column("is_custom_item")

    with op.batch_alter_table("estimate_line_items") as batch_op:
        batch_op.drop_column("applied_margin_percent")
        batch_op.drop_column("pricing_rule_applied")
        batch_op.drop_column("is_custom_item")

    with op.batch_alter_table("estimates") as batch_op:
        batch_op.drop_column("margin_percent_override")

    op.drop_table("client_product_rates")
