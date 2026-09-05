"""Add client_documents - a genuine gap against the explicit
task list and its "protect unauthorized documents" security item.
Multiple documents per client (unlike the candidate resume's 1:1
pattern), reusing the same stored-filename/path-traversal protection
already established for resume uploads.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "client_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("client_documents")
