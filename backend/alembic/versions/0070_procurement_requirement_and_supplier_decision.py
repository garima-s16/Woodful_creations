"""Two new tables for P0.2.1/P0.2.3, closing the two gaps this
family's own review identified: there was no persisted Procurement
Requirement (the "requirement" was only ever a transient calculation
result) and no persisted Supplier Decision (a Purchase's supplier_id
alone cannot say whether the recommendation was followed).

Genuinely new tables, not additions to any existing one -
create_table_if_missing is idempotent, matching the established
pattern from 0059_chat_learning_candidates.py / 0065_report_history.py.

Revision ID: 0070
Revises: 0069
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "procurement_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("required_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("available_quantity_at_creation", sa.Numeric(12, 2), nullable=False),
        sa.Column("shortage_quantity_at_creation", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("required_by_date", sa.DateTime(), nullable=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
    )
    create_index_if_missing(bind, "ix_procurement_requirements_business_id", "procurement_requirements", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_procurement_requirements_order_id", "procurement_requirements", ["order_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_material_id", "procurement_requirements", ["material_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_status", "procurement_requirements", ["status"])
    create_index_if_missing(bind, "ix_procurement_requirements_purchase_id", "procurement_requirements", ["purchase_id"])

    create_table_if_missing(
        bind,
        "supplier_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("procurement_requirements.id"), nullable=False),
        sa.Column("recommended_supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("recommended_reason", sa.String(255), nullable=True),
        sa.Column("selected_supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("decision_reason", sa.String(255), nullable=True),
        sa.Column("decided_by", sa.String(255), nullable=True),
    )
    create_index_if_missing(bind, "ix_supplier_decisions_business_id", "supplier_decisions", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_supplier_decisions_requirement_id", "supplier_decisions", ["requirement_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_supplier_decisions_requirement_id", table_name="supplier_decisions")
    op.drop_index("ix_supplier_decisions_business_id", table_name="supplier_decisions")
    op.drop_table("supplier_decisions")
    op.drop_index("ix_procurement_requirements_purchase_id", table_name="procurement_requirements")
    op.drop_index("ix_procurement_requirements_status", table_name="procurement_requirements")
    op.drop_index("ix_procurement_requirements_material_id", table_name="procurement_requirements")
    op.drop_index("ix_procurement_requirements_order_id", table_name="procurement_requirements")
    op.drop_index("ix_procurement_requirements_business_id", table_name="procurement_requirements")
    op.drop_table("procurement_requirements")
