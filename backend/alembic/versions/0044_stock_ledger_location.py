"""Add location_id to stock_ledger_entries, purchases, issues, and
stock_adjustments - true multi-location stock.

Material.location_id remains as the single "primary location" field for
backward compatibility (existing dashboards/PDF/chatbot reads keep working
unchanged). This migration only adds the column ledger entries need to
record WHERE a movement happened, so per-location balances can be derived
by summing quantity_delta grouped by location_id. No existing data is
touched - old ledger rows simply have location_id = NULL, and callers that
need a location for them fall back to the material's current location_id
at read time (see StockService.get_location_balances).

Each of these four columns has an inline ForeignKey to locations.id -
SQLite cannot add a column with a constraint via a plain ALTER TABLE
(the same reasoning migrations 0004/0012/0016/0018/0026 already
document at length), so this needs batch_alter_table with a naming
convention for each of the four tables, not migration_guards'
add_column_if_missing (which issues a plain op.add_column - correct
for a column with no constraint, but not sufficient here).

Revision ID: 0044
Revises: 0043
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa
from app.core.migration_guards import column_exists, index_exists

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# (table, index_name)
_TARGETS = [
    ("stock_ledger_entries", "ix_stock_ledger_entries_location_id"),
    ("purchases", "ix_purchases_location_id"),
    ("issues", "ix_issues_location_id"),
    ("stock_adjustments", "ix_stock_adjustments_location_id"),
]


def _add_location_column(bind, table, index_name):
    if column_exists(bind, table, "location_id"):
        # Column already present - only the index might still be
        # missing (e.g. an interrupted prior run), and creating an
        # index alone does not need batch mode.
        if not index_exists(bind, table, index_name):
            op.create_index(index_name, table, ["location_id"])
        return
    with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column(
            "location_id", sa.Integer(),
            sa.ForeignKey("locations.id", name=f"fk_{table}_location_id_locations"),
            nullable=True,
        ))
        batch_op.create_index(index_name, ["location_id"])


def upgrade() -> None:
    bind = op.get_bind()
    for table, index_name in _TARGETS:
        _add_location_column(bind, table, index_name)


def downgrade() -> None:
    bind = op.get_bind()
    for table, index_name in reversed(_TARGETS):
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
            if index_exists(bind, table, index_name):
                batch_op.drop_index(index_name)
            if column_exists(bind, table, "location_id"):
                batch_op.drop_column("location_id")
