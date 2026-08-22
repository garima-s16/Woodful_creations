"""Add SupplierMaterial - the real many-to-many between Supplier and
Material (Section 7): a supplier can supply many materials, a material
can have many suppliers, each pairing carrying its own SKU, price,
MOQ, lead time, and preferred status.

Distinct from and does not replace Material.supplier_id (the existing
single "primary supplier" field) - that stays exactly as-is for
backward compatibility with every existing consumer. This is
additive: a fresh CREATE TABLE with two foreign keys, both natively
supported since it's a new table, not an ALTER on an existing one.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "supplier_materials",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("supplier_sku", sa.String(100), nullable=True),
        sa.Column("supplier_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_purchase_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("moq", sa.Integer(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("supplier_id", "material_id", name="uq_supplier_material_pair"),
    )
    create_index_if_missing(bind, "ix_supplier_materials_supplier_id", "supplier_materials", ["supplier_id"])
    create_index_if_missing(bind, "ix_supplier_materials_material_id", "supplier_materials", ["material_id"])


def downgrade() -> None:
    op.drop_table("supplier_materials")
