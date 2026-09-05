"""Add estimate versioning (version, parent_estimate_id) and the
client_activities table (client communication/interaction log).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database.migration_guards import create_table_if_missing, column_exists

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # SQLite does not support adding a column with a foreign key
    # constraint via a plain ALTER TABLE - batch mode works around this
    # (by rebuilding the table under the hood) and behaves identically
    # on PostgreSQL, so this is safe for both backends this project uses.
    #
    # Batch mode reflects the table as it actually exists in the database
    # to build the replacement, and SQLite genuinely stores no name for a
    # constraint that was created without one. The original `estimates`
    # table (migration 0002) has two unnamed foreign keys (client_id,
    # order_id) and a unique constraint (estimate_code) with no explicit
    # name either - this is Alembic's own documented naming_convention,
    # covering every constraint type batch mode might need to name
    # during reflection, not just foreign keys.
    naming_convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
    # Both columns (and the index) are added together in this one batch
    # op - checking just the first is enough to know whether the whole
    # block already ran (they were always added atomically here).
    if not column_exists(bind, "estimates", "version"):
        with op.batch_alter_table("estimates", naming_convention=naming_convention) as batch_op:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
            batch_op.add_column(sa.Column(
                "parent_estimate_id", sa.Integer(),
                sa.ForeignKey("estimates.id", name="fk_estimates_parent_estimate_id"),
                nullable=True,
            ))
            batch_op.create_index("ix_estimates_parent_estimate_id", ["parent_estimate_id"])

    create_table_if_missing(
        bind, "client_activities",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("activity_type", sa.String(30), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("logged_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("client_activities")
    naming_convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
    with op.batch_alter_table("estimates", naming_convention=naming_convention) as batch_op:
        batch_op.drop_index("ix_estimates_parent_estimate_id")
        batch_op.drop_column("parent_estimate_id")
        batch_op.drop_column("version")
