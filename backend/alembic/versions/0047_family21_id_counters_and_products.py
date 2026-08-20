"""Family 21 - Data Foundation + Product Master.

- id_counters: single-row atomic counter backing the now-incremental,
  centralized generate_short_id() (see utils/id_generator.py). Seeded
  with one "global" row so every entity type shares one strictly-
  increasing sequence.
- product_categories / product_subcategories / products /
  product_materials: the real Product Master (standard + custom
  furniture, categories/subcategories, dimensions, finish, unit, BOM,
  costing, active flag).
- order_items.product_id / estimate_line_items.product_id: the
  Product <-> Order Item / Estimate Line Item relationship, nullable so
  a genuinely custom one-off line can still exist with no catalog entry.

Revision ID: 0047
Revises: 0046
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "id_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("next_value", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_id_counters_name", "id_counters", ["name"], unique=True)
    op.execute(
        "INSERT INTO id_counters (name, next_value, created_at, updated_at) "
        "VALUES ('global', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_product_categories_business_id", "product_categories", ["business_id"], unique=True)
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=True)

    op.create_table(
        "product_subcategories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("product_categories.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("category_id", "name", name="uq_product_subcategory_per_category"),
    )
    op.create_index("ix_product_subcategories_business_id", "product_subcategories", ["business_id"], unique=True)
    op.create_index("ix_product_subcategories_category_id", "product_subcategories", ["category_id"])
    op.create_index("ix_product_subcategories_name", "product_subcategories", ["name"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_code", sa.String(20), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("sku", sa.String(50), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("product_subcategories.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specifications", sa.Text(), nullable=True),
        sa.Column("length", sa.Numeric(10, 2), nullable=True),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("dimension_unit", sa.String(10), nullable=False, server_default="in"),
        sa.Column("finish", sa.String(150), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="Piece"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default="18"),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
    )
    op.create_index("ix_products_product_code", "products", ["product_code"], unique=True)
    op.create_index("ix_products_business_id", "products", ["business_id"], unique=True)
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_product_type", "products", ["product_type"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_subcategory_id", "products", ["subcategory_id"])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "product_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.UniqueConstraint("product_id", "material_id", name="uq_product_material"),
    )
    op.create_index("ix_product_materials_product_id", "product_materials", ["product_id"])
    op.create_index("ix_product_materials_material_id", "product_materials", ["material_id"])

    with op.batch_alter_table("order_items") as batch_op:
        batch_op.add_column(sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True))
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    with op.batch_alter_table("estimate_line_items") as batch_op:
        batch_op.add_column(sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True))
    op.create_index("ix_estimate_line_items_product_id", "estimate_line_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_estimate_line_items_product_id", table_name="estimate_line_items")
    with op.batch_alter_table("estimate_line_items") as batch_op:
        batch_op.drop_column("product_id")

    op.drop_index("ix_order_items_product_id", table_name="order_items")
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_column("product_id")

    op.drop_table("product_materials")

    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_index("ix_products_subcategory_id", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_product_type", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_index("ix_products_business_id", table_name="products")
    op.drop_index("ix_products_product_code", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_product_subcategories_name", table_name="product_subcategories")
    op.drop_index("ix_product_subcategories_category_id", table_name="product_subcategories")
    op.drop_index("ix_product_subcategories_business_id", table_name="product_subcategories")
    op.drop_table("product_subcategories")

    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.drop_index("ix_product_categories_business_id", table_name="product_categories")
    op.drop_table("product_categories")

    op.drop_index("ix_id_counters_name", table_name="id_counters")
    op.drop_table("id_counters")
