"""Add estimate versioning (version, parent_estimate_id) and the
client_activities table (client communication/interaction log).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite does not support adding a column with a foreign key
    # constraint via a plain ALTER TABLE - batch mode works around this
    # (by rebuilding the table under the hood) and behaves identically
    # on PostgreSQL, so this is safe for both backends this project uses.
    with op.batch_alter_table("estimates") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("parent_estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=True))
        batch_op.create_index("ix_estimates_parent_estimate_id", ["parent_estimate_id"])

    op.create_table(
        "client_activities",
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
    with op.batch_alter_table("estimates") as batch_op:
        batch_op.drop_index("ix_estimates_parent_estimate_id")
        batch_op.drop_column("parent_estimate_id")
        batch_op.drop_column("version")
