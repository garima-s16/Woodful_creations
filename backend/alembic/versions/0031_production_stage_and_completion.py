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

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

STAGES = ["Cutting", "CNC / Drilling", "Edge Banding", "Assembly", "Finishing", "QC", "Packing", "Dispatch"]


def upgrade() -> None:
    op.add_column("production_jobs", sa.Column("stage", sa.String(50), nullable=True))
    op.add_column("production_jobs", sa.Column("completion_date", sa.DateTime(), nullable=True))

    op.create_table(
        "production_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    stages_table = sa.table(
        "production_stages",
        sa.column("name", sa.String), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    now = sa.func.now()
    op.bulk_insert(stages_table, [{"name": s, "created_at": now, "updated_at": now} for s in STAGES])


def downgrade() -> None:
    op.drop_table("production_stages")
    op.drop_column("production_jobs", "completion_date")
    op.drop_column("production_jobs", "stage")
