"""Freeze the material rate on each Issue at
the moment it's recorded (issues.rate_at_issue), so a later purchase
changing a material's current average_rate can never retroactively
change what an already-recorded issue is understood to have cost.
order_service.py's profitability() calculation now reads this frozen
value instead of deriving cost from the material's current
average_rate at query time.

Existing issue rows predate this column and have no way to recover
their true historical rate (it was never recorded) - each is backfilled
with its material's CURRENT average_rate as the best available
approximation, matching migration 0061's same philosophy for its own
backfill: this preserves today's existing displayed profitability
numbers exactly (no visible change at migration time), while every new
issue going forward gets a genuinely frozen, permanent value that
later purchases cannot silently alter.

Revision ID: 0064
Revises: 0063
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import add_column_if_missing, table_exists

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "issues"):
        return

    add_column_if_missing(bind, "issues", sa.Column("rate_at_issue", sa.Numeric(12, 2), nullable=True))

    if table_exists(bind, "materials"):
        bind.execute(sa.text(
            "UPDATE issues SET rate_at_issue = ("
            "  SELECT materials.average_rate FROM materials WHERE materials.id = issues.material_id"
            ") WHERE issues.rate_at_issue IS NULL"
        ))


def downgrade() -> None:
    with op.batch_alter_table("issues") as batch_op:
        batch_op.drop_column("rate_at_issue")
