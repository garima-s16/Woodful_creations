"""Add structured interview feedback fields (Priority 8) - overall/
technical/communication/culture-fit ratings, strengths/weaknesses/
observations, and a controlled recommendation value. Previously
Interview had a single free-text `feedback` column, which is kept
(not dropped) for any existing notes and as a general-notes field
alongside the new structured ones.

All plain nullable columns with no inline constraints, so this is
safe via a direct ALTER TABLE without needing SQLite batch mode.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import add_column_if_missing

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "interviews", sa.Column("overall_rating", sa.Integer(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("technical_rating", sa.Integer(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("communication_rating", sa.Integer(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("culture_fit_rating", sa.Integer(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("strengths", sa.Text(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("weaknesses", sa.Text(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("observations", sa.Text(), nullable=True))
    add_column_if_missing(bind, "interviews", sa.Column("recommendation", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "recommendation")
    op.drop_column("interviews", "observations")
    op.drop_column("interviews", "weaknesses")
    op.drop_column("interviews", "strengths")
    op.drop_column("interviews", "culture_fit_rating")
    op.drop_column("interviews", "communication_rating")
    op.drop_column("interviews", "technical_rating")
    op.drop_column("interviews", "overall_rating")
