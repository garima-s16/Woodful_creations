"""A new table for the chatbot's
controlled learning-candidate mechanism. Stores only a user's phrase,
its normalized form, and the tool name Gemini resolved it to - never
business data (amounts, IDs, contact details), per Section 24.

A genuinely new table, not an addition to any existing one -
create_table_if_missing is idempotent, matching the established
pattern from 0001_initial_schema.py.

Revision ID: 0059
Revises: 0058
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "chat_learning_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("normalized_phrase", sa.String(500), nullable=False),
        sa.Column("resolved_tool", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    create_index_if_missing(
        bind, "ix_chat_learning_candidates_phrase", "chat_learning_candidates", ["phrase"]
    )
    create_index_if_missing(
        bind, "ix_chat_learning_candidates_normalized_phrase", "chat_learning_candidates", ["normalized_phrase"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_learning_candidates_normalized_phrase", table_name="chat_learning_candidates")
    op.drop_index("ix_chat_learning_candidates_phrase", table_name="chat_learning_candidates")
    op.drop_table("chat_learning_candidates")
