"""Add generic_documents - covers order/supplier/purchase/employee
documents in one polymorphic table, rather than a near-identical
dedicated table for each (matching Family 10's explicit "project
documents", "supplier documents", "purchase documents", "employee
documents" task items). Client and payment documents already have
their own established, tested tables and are deliberately left
as-is here.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "generic_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_type", sa.String(20), nullable=False, index=True),
        sa.Column("parent_id", sa.Integer(), nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    create_index_if_missing(bind, "ix_generic_documents_parent", "generic_documents", ["parent_type", "parent_id"])


def downgrade() -> None:
    op.drop_index("ix_generic_documents_parent", table_name="generic_documents")
    op.drop_table("generic_documents")
