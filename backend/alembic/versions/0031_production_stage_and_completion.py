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

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

STAGES = ["Cutting", "CNC / Drilling", "Edge Banding", "Assembly", "Finishing", "QC", "Packing", "Dispatch"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Guard each piece individually (rather than letting an "already
    # exists" error on one column abort the whole migration) so the
    # production_stages seed data below always gets a chance to run, even
    # on a legacy database whose tables were created via create_all()
    # against already-current models - otherwise this lookup table would
    # be silently created empty and never seeded.
    existing_columns = {c["name"] for c in inspector.get_columns("production_jobs")}
    if "stage" not in existing_columns:
        op.add_column("production_jobs", sa.Column("stage", sa.String(50), nullable=True))
    if "completion_date" not in existing_columns:
        op.add_column("production_jobs", sa.Column("completion_date", sa.DateTime(), nullable=True))

    if "production_stages" not in inspector.get_table_names():
        op.create_table(
            "production_stages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # Re-check row count regardless of whether the table was just created
    # above or already existed (e.g. created empty by create_all()) - only
    # seed the defaults if genuinely empty, so this is safe to run
    # against a table that already has this data.
    existing_row_count = bind.execute(sa.text("SELECT COUNT(*) FROM production_stages")).scalar()
    if existing_row_count == 0:
        stages_table = sa.table(
            "production_stages",
            sa.column("name", sa.String), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        )
        # A real Python datetime, not sa.func.now(): SQLite's DBAPI binds
        # bulk_insert parameters directly (no server-side NOW() function
        # to fall back on the way Postgres/MySQL would), so passing the
        # SQL-expression object itself here raises a StatementError at
        # runtime instead of inserting a timestamp. datetime.utcnow(),
        # matching the same seeding convention already used in
        # 0016_material_category_hierarchy.py and 0030_working_calendar.py.
        now = datetime.utcnow()
        op.bulk_insert(stages_table, [{"name": s, "created_at": now, "updated_at": now} for s in STAGES])


def downgrade() -> None:
    op.drop_table("production_stages")
    op.drop_column("production_jobs", "completion_date")
    op.drop_column("production_jobs", "stage")
