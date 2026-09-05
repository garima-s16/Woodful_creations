"""Freeze historical stock-location attribution so it no longer drifts
when a material's current primary location changes later.

Two related gaps existed:

1. StockLedgerEntry rows written before multi-location support existed
   have location_id = NULL. StockService derived their location at read
   time as `entry.location_id or material.location_id` - using the
   material's CURRENT primary location. If that location is later
   changed (Material.location_id is a normal, freely editable field),
   these old rows silently appear to have "moved" to the new location,
   even though nothing about the historical transaction changed.

2. Material.opening_stock has the same problem: it predates the ledger
   and carries no location of its own, so it was always attributed to
   the material's current location_id at read time - same drift risk.

This migration performs a one-time, static backfill instead of a
dynamic one:

- Every StockLedgerEntry with location_id IS NULL, for a material that
  currently has a location_id, is stamped with that material's
  location_id once, now. This preserves today's existing displayed
  balances exactly (no visible change), but the assignment is now a
  permanent fact about the row instead of something recomputed against
  a value that can keep changing. Legacy entries for a material that
  has never had any location remain NULL - genuinely unknown, shown as
  "Unassigned" - rather than fabricating one.

- A new Material.opening_stock_location_id column records where the
  opening stock balance belongs, snapshotted once from the material's
  location_id at migration time for existing rows. Going forward,
  MaterialCreate captures this at creation time and it is never
  implicitly re-derived from the (mutable) primary location afterwards.

No ledger entries or transactions are deleted or rewritten - only a
NULL location_id is filled in, and only where it was previously being
assumed anyway at read time.

Revision ID: 0061
Revises: 0060
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import add_column_if_missing, table_exists

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "materials"):
        add_column_if_missing(
            bind, "materials",
            sa.Column("opening_stock_location_id", sa.Integer(),
                      sa.ForeignKey("locations.id", name="fk_materials_opening_stock_location_id_locations"),
                      nullable=True),
        )
        bind.execute(sa.text(
            "UPDATE materials SET opening_stock_location_id = location_id "
            "WHERE opening_stock_location_id IS NULL AND location_id IS NOT NULL"
        ))

    if table_exists(bind, "stock_ledger_entries") and table_exists(bind, "materials"):
        bind.execute(sa.text(
            "UPDATE stock_ledger_entries "
            "SET location_id = ("
            "  SELECT materials.location_id FROM materials "
            "  WHERE materials.id = stock_ledger_entries.material_id"
            ") "
            "WHERE stock_ledger_entries.location_id IS NULL "
            "AND EXISTS ("
            "  SELECT 1 FROM materials "
            "  WHERE materials.id = stock_ledger_entries.material_id "
            "  AND materials.location_id IS NOT NULL"
            ")"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    # The backfill itself is not reversible (we no longer know which
    # rows were originally NULL) - only the added column is removed.
    if table_exists(bind, "materials"):
        with op.batch_alter_table("materials") as batch_op:
            batch_op.drop_column("opening_stock_location_id")
