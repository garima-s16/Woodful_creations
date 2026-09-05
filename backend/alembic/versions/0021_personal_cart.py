"""Add PersonalCartItem - the database-backed personal cart (real
persistence, per user, survives logout/login/browser refresh - never
localStorage/Redux-only). Fresh CREATE TABLE with FKs, natively
supported since it's a new table, not an ALTER on an existing one.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "personal_cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("material_name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_name", sa.String(255), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
    )
    create_index_if_missing(bind, "ix_personal_cart_items_user_id", "personal_cart_items", ["user_id"])
    create_index_if_missing(bind, "ix_personal_cart_items_material_id", "personal_cart_items", ["material_id"])


def downgrade() -> None:
    op.drop_table("personal_cart_items")
