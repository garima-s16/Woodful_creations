"""One-estimate-per-order invariant - adds a database-level
unique index on estimates.order_id, confirmed (not merely assumed from
a comment) to be the application's actual, existing invariant: the
only place order_id is ever set is the estimate-to-order conversion
workflow in orders.py, which always creates a brand-new Order for each
conversion, and EstimateUpdate's own schema doesn't expose order_id as
a settable field at all - there is no exposed path through which two
estimates could come to share the same order_id today.

A standard unique index on a nullable column still permits multiple
NULLs (every not-yet-converted estimate), enforcing uniqueness only
among the real, non-null values - exactly the intended semantic. This
is a defense-in-depth addition protecting an already-true invariant
against a future code change accidentally weakening it, not a change
in current behavior.

Any pre-existing conflicting rows (which the code-level verification
above suggests should not exist, but is not assumed) are resolved
safely before the index is created: the most recently updated
estimate per conflicting order_id is kept linked, the others have
their order_id cleared (not deleted) - each resolution logged.

Revision ID: 0067
Revises: 0066
Create Date: 2026-08-29
"""
import logging
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import table_exists, index_exists

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration.0067")

INDEX_NAME = "ix_estimates_order_id_unique"


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "estimates"):
        return

    duplicate_orders = bind.execute(sa.text(
        "SELECT order_id, COUNT(*) as cnt FROM estimates "
        "WHERE order_id IS NOT NULL GROUP BY order_id HAVING COUNT(*) > 1"
    )).fetchall()

    for order_id, _count in duplicate_orders:
        rows = bind.execute(
            sa.text("SELECT id FROM estimates WHERE order_id = :oid ORDER BY updated_at DESC"),
            {"oid": order_id},
        ).fetchall()
        row_ids = [r[0] for r in rows]
        keep_id, clear_ids = row_ids[0], row_ids[1:]
        logger.warning(
            "Duplicate order_id link resolved for order_id=%s: "
            "kept estimate #%s linked (most recently updated), cleared order_id on %s",
            order_id, keep_id, clear_ids,
        )
        for clear_id in clear_ids:
            bind.execute(sa.text("UPDATE estimates SET order_id = NULL WHERE id = :eid"), {"eid": clear_id})

    if not index_exists(bind, "estimates", INDEX_NAME):
        op.create_index(INDEX_NAME, "estimates", ["order_id"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="estimates")
