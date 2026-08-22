"""Add payment_documents - genuine gap against Family 8's explicit
"protect transaction documents" security item, which implies such
documents should exist. Proof of payment (cheque scan, UPI
screenshot, bank transfer receipt), reusing the exact same
stored-filename/path-traversal protection already established for
client documents and candidate resumes.

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import create_table_if_missing

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "payment_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("payment_documents")
