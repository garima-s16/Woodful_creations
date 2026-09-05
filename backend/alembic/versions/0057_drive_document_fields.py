"""Google Drive support fields on the existing document
tables (generic_documents, client_documents, payment_documents).

Adds two columns to each, not a new table - Section 44's explicit "no
duplicate document system" requirement. All three tables already share
an identical shape (original_filename, stored_filename, content_type,
description, uploaded_by), confirmed by reading each model before
writing this migration.

storage_backend distinguishes where the file actually lives ("local"
default, or "drive" once successfully uploaded to Google Drive) -
existing rows implicitly stay "local" via the server_default, so this
never reinterprets already-stored files. drive_file_id is nullable and
only ever populated when storage_backend="drive" - Neon stores the
reference, never the file content itself (Section 17).

Revision ID: 0057
Revises: 0056
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing, create_index_if_missing

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

TABLES = ["generic_documents", "client_documents", "payment_documents"]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        add_column_if_missing(
            bind, table,
            sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        )
        add_column_if_missing(bind, table, sa.Column("drive_file_id", sa.String(255), nullable=True))
        create_index_if_missing(bind, f"ix_{table}_drive_file_id", table, ["drive_file_id"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_drive_file_id", table_name=table)
        op.drop_column(table, "drive_file_id")
        op.drop_column(table, "storage_backend")
