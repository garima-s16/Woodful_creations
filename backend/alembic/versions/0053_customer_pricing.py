"""Customer-specific pricing (client_product_rates), Estimate margin
override, and historical pricing-provenance snapshot fields on
estimate/order line items (is_custom_item, pricing_rule_applied,
applied_margin_percent).

client_product_rates.product_id is nullable: a row with product_id
NULL is a client-wide default margin (e.g. "this client always gets
15%, regardless of product"), distinct from a row with a specific
product_id, which overrides just that one product for that one
client.

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing, column_exists

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

# Required for batch_alter_table on SQLite - even when the column(s)
# being added here have no FK of their own, SQLite's batch mode
# rebuilds the whole table and must reflect and name every EXISTING
# constraint on it (estimates/estimate_line_items/order_items all
# already carry unnamed foreign keys from earlier migrations). Same
# convention as migrations 0004/0012/0016/0048.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind, "client_product_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(),
                  sa.ForeignKey("clients.id", name="fk_client_product_rates_client_id_clients"),
                  nullable=False, index=True),
        sa.Column("product_id", sa.Integer(),
                  sa.ForeignKey("products.id", name="fk_client_product_rates_product_id_products"),
                  nullable=True, index=True),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("fixed_selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("client_id", "product_id", name="uq_client_product_rate"),
    )

    if not column_exists(bind, "estimates", "margin_percent_override"):
        with op.batch_alter_table("estimates", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("margin_percent_override", sa.Numeric(5, 2), nullable=True))

    if not column_exists(bind, "estimate_line_items", "is_custom_item"):
        with op.batch_alter_table("estimate_line_items", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()))
            batch_op.add_column(sa.Column("pricing_rule_applied", sa.String(40), nullable=True))
            batch_op.add_column(sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True))

    if not column_exists(bind, "order_items", "is_custom_item"):
        with op.batch_alter_table("order_items", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()))
            batch_op.add_column(sa.Column("pricing_rule_applied", sa.String(40), nullable=True))
            batch_op.add_column(sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_items", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("applied_margin_percent")
        batch_op.drop_column("pricing_rule_applied")
        batch_op.drop_column("is_custom_item")

    with op.batch_alter_table("estimate_line_items", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("applied_margin_percent")
        batch_op.drop_column("pricing_rule_applied")
        batch_op.drop_column("is_custom_item")

    with op.batch_alter_table("estimates", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("margin_percent_override")

    op.drop_table("client_product_rates")
