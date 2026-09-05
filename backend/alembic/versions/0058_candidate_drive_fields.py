"""Google Drive support fields on candidates, completing
what migration 0057 did for generic_documents/client_documents/
payment_documents. candidates was the one remaining document-bearing
table without storage_backend/drive_file_id (confirmed by reading the
model before writing this migration), per Section 15's explicit
"ensure Candidate also has the storage information required for
Drive" requirement.

Same reasoning as 0057: storage_backend defaults "local" via
server_default so every existing candidate row (which has no Drive
upload) stays correctly "local", never silently becomes "drive".
drive_file_id is nullable and only populated once a resume is
actually uploaded to Drive.

Revision ID: 0058
Revises: 0057
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing, create_index_if_missing

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(
        bind, "candidates",
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
    )
    add_column_if_missing(bind, "candidates", sa.Column("drive_file_id", sa.String(255), nullable=True))
    create_index_if_missing(bind, "ix_candidates_drive_file_id", "candidates", ["drive_file_id"])


def downgrade() -> None:
    op.drop_index("ix_candidates_drive_file_id", table_name="candidates")
    op.drop_column("candidates", "drive_file_id")
    op.drop_column("candidates", "storage_backend")
