"""Add the Product Master: products, product_materials
(bill-of-materials link to the existing Material Stock Master), and
optional product_id references on order_items / estimate_line_items so
an order/estimate can identify exactly what was ordered/quoted.

Revision ID: 0048
Revises: 0047
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, column_exists, index_exists

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

# Required for batch_alter_table on SQLite whenever the rebuilt table
# has (or gains) a foreign key - SQLite stores no name for a
# constraint created without one, so Alembic needs this to reflect and
# name every constraint on the table being rebuilt, not just the new
# one. Same convention as migrations 0004/0012/0016.
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
        bind, "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_code", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("business_id", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("product_type", sa.String(20), nullable=False, server_default="standard", index=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("subcategory", sa.String(100), nullable=True, index=True),
        sa.Column("specifications", sa.Text(), nullable=True),
        sa.Column("length", sa.Numeric(10, 2), nullable=True),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("dimension_unit", sa.String(10), nullable=True, server_default="in"),
        sa.Column("primary_material", sa.String(150), nullable=True),
        sa.Column("finish", sa.String(150), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="Nos"),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("hardware_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("labour_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("machine_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("finish_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("packing_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("transport_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("overhead_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    create_table_if_missing(
        bind, "product_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False, index=True),
        sa.Column("quantity_required", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.UniqueConstraint("product_id", "material_id", name="uq_product_material_pair"),
    )

    if not column_exists(bind, "order_items", "product_id"):
        with op.batch_alter_table("order_items", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column(
                "product_id", sa.Integer(),
                sa.ForeignKey("products.id", name="fk_order_items_product_id_products"), nullable=True,
            ))
            batch_op.create_index("ix_order_items_product_id", ["product_id"])
    elif not index_exists(bind, "order_items", "ix_order_items_product_id"):
        op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    if not column_exists(bind, "estimate_line_items", "product_id"):
        with op.batch_alter_table("estimate_line_items", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column(
                "product_id", sa.Integer(),
                sa.ForeignKey("products.id", name="fk_estimate_line_items_product_id_products"), nullable=True,
            ))
            batch_op.create_index("ix_estimate_line_items_product_id", ["product_id"])
    elif not index_exists(bind, "estimate_line_items", "ix_estimate_line_items_product_id"):
        op.create_index("ix_estimate_line_items_product_id", "estimate_line_items", ["product_id"])


def downgrade() -> None:
    with op.batch_alter_table("estimate_line_items", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_estimate_line_items_product_id")
        batch_op.drop_column("product_id")

    with op.batch_alter_table("order_items", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_order_items_product_id")
        batch_op.drop_column("product_id")

    op.drop_table("product_materials")
    op.drop_table("products")
