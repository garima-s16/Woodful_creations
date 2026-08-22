"""Add real resume upload fields to Candidate (Priority 7) - the app had
a resume_url text field the user had to paste a link into, and
MAX_UPLOAD_SIZE/UPLOAD_DIRECTORY/ALLOWED_EXTENSIONS already existed in
config.py but were never wired into any actual upload route. resume_url
is kept for backward compatibility (a candidate's resume may genuinely
be an external link) alongside the new fields for an actually-uploaded
file.

All plain nullable columns, no inline constraints - safe via a direct
ALTER TABLE without needing SQLite batch mode.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import add_column_if_missing

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "candidates", sa.Column("resume_stored_filename", sa.String(255), nullable=True))
    add_column_if_missing(bind, "candidates", sa.Column("resume_original_filename", sa.String(255), nullable=True))
    add_column_if_missing(bind, "candidates", sa.Column("resume_content_type", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "resume_content_type")
    op.drop_column("candidates", "resume_original_filename")
    op.drop_column("candidates", "resume_stored_filename")
