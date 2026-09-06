"""A new table for P0.3.5 - configurable production
resources (CNC, Cutting, Edge Banding, Assembly, Finishing, or
whatever this business actually has, never a hardcoded list), plus an
optional link from production_operations to a real WorkCentre,
additive alongside the existing free-text resource column so no
existing row needs a backfill.

Revision ID: 0069
Revises: 0068
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing, add_column_if_missing, table_exists

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(
        bind,
        "work_centres",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capacity_hours_per_day", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    create_index_if_missing(bind, "ix_work_centres_business_id", "work_centres", ["business_id"], unique=True)
    create_index_if_missing(bind, "ix_work_centres_name", "work_centres", ["name"], unique=True)

    if table_exists(bind, "production_operations"):
        add_column_if_missing(
            bind, "production_operations",
            sa.Column("work_centre_id", sa.Integer(),
                      sa.ForeignKey("work_centres.id", name="fk_production_operations_work_centre_id"),
                      nullable=True),
        )
        create_index_if_missing(bind, "ix_production_operations_work_centre_id", "production_operations", ["work_centre_id"])


def downgrade() -> None:
    op.drop_index("ix_production_operations_work_centre_id", table_name="production_operations")
    with op.batch_alter_table("production_operations") as batch_op:
        batch_op.drop_column("work_centre_id")
    op.drop_index("ix_work_centres_name", table_name="work_centres")
    op.drop_index("ix_work_centres_business_id", table_name="work_centres")
    op.drop_table("work_centres")
