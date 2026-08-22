"""Add production_stages lookup table plus stage and completion_date
on production_jobs - the brief's explicit pipeline vocabulary
(Cutting/CNC-Drilling/Edge Banding/Assembly/Finishing/QC/Packing/
Dispatch), standardized and distinct from the free-text operation
description, plus the same "actual completion timestamp" gap already
fixed on daily_tasks.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
from app.core.migration_guards import create_table_if_missing, add_column_if_missing

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

STAGES = ["Cutting", "CNC / Drilling", "Edge Banding", "Assembly", "Finishing", "QC", "Packing", "Dispatch"]


def upgrade() -> None:
    bind = op.get_bind()
    add_column_if_missing(bind, "production_jobs", sa.Column("stage", sa.String(50), nullable=True))
    add_column_if_missing(bind, "production_jobs", sa.Column("completion_date", sa.DateTime(), nullable=True))

    create_table_if_missing(
        bind, "production_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Guard against re-inserting the same stage names on a second run -
    # name has a unique constraint, so an unconditional insert would fail.
    existing_row_count = bind.execute(sa.text("SELECT COUNT(*) FROM production_stages")).scalar()
    if existing_row_count == 0:
        stages_table = sa.table(
            "production_stages",
            sa.column("name", sa.String), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        )
        # A real Python datetime value, not sa.func.now() (a SQL
        # expression object) - same fix as migration 0030 needed.
        now = datetime.utcnow()
        op.bulk_insert(stages_table, [{"name": s, "created_at": now, "updated_at": now} for s in STAGES])


def downgrade() -> None:
    op.drop_table("production_stages")
    op.drop_column("production_jobs", "completion_date")
    op.drop_column("production_jobs", "stage")
