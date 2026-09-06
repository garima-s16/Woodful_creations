"""A new table for P0.3 section 25 - Cutting: one row per part that
needs to be cut from a material sheet, with real dimensions (mm),
grain direction, and rotation constraint - never stored only as free
text. Creating a row here does not touch physical stock.

Revision ID: 0071
Revises: 0070
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "cutting_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("production_job_id", sa.Integer(), sa.ForeignKey("production_jobs.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("part_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("length_mm", sa.Numeric(10, 2), nullable=False),
        sa.Column("width_mm", sa.Numeric(10, 2), nullable=False),
        sa.Column("thickness_mm", sa.Numeric(10, 2), nullable=True),
        sa.Column("grain_direction", sa.String(20), nullable=True),
        sa.Column("rotation_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("kerf_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    create_index_if_missing(bind, "ix_cutting_requirements_business_id", "cutting_requirements", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_cutting_requirements_production_job_id", "cutting_requirements", ["production_job_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_product_id", "cutting_requirements", ["product_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_material_id", "cutting_requirements", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_cutting_requirements_material_id", table_name="cutting_requirements")
    op.drop_index("ix_cutting_requirements_product_id", table_name="cutting_requirements")
    op.drop_index("ix_cutting_requirements_production_job_id", table_name="cutting_requirements")
    op.drop_index("ix_cutting_requirements_business_id", table_name="cutting_requirements")
    op.drop_table("cutting_requirements")
