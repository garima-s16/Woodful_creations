"""Client-wide pricing concurrency - at most one
client-wide default product rate (product_id IS NULL) per client,
enforced at the database level via a partial unique index. The
existing UniqueConstraint("client_id", "product_id") does not prevent
two client-wide rows for the same client, since standard SQL treats
NULL as distinct from NULL in uniqueness comparisons - this was
already noted in the model's own comment. The existing
application-level check (read, see nothing, insert) is vulnerable to
two concurrent requests both passing the check before either commits;
this migration adds the missing database-level invariant.

Before creating the index, any pre-existing duplicate client-wide rows
are resolved: the most recently updated row per client is kept as
authoritative, others are removed - but never silently. Each removal
is logged, matching the same discipline used in the attendance
uniqueness migration.

Portable across both SQLite (tests) and PostgreSQL (production) -
both support `CREATE UNIQUE INDEX ... WHERE ...` partial index syntax.

Revision ID: 0066
Revises: 0065
Create Date: 2026-08-29
"""
import logging
from alembic import op
import sqlalchemy as sa

from app.platform.database.migration_guards import table_exists, index_exists

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.migration.0066")

INDEX_NAME = "ix_client_product_rates_one_default_per_client"


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "client_product_rates"):
        return

    duplicate_clients = bind.execute(sa.text(
        "SELECT client_id, COUNT(*) as cnt FROM client_product_rates "
        "WHERE product_id IS NULL GROUP BY client_id HAVING COUNT(*) > 1"
    )).fetchall()

    for client_id, _count in duplicate_clients:
        rows = bind.execute(
            sa.text(
                "SELECT id FROM client_product_rates "
                "WHERE client_id = :cid AND product_id IS NULL ORDER BY updated_at DESC"
            ),
            {"cid": client_id},
        ).fetchall()
        row_ids = [r[0] for r in rows]
        keep_id, remove_ids = row_ids[0], row_ids[1:]
        logger.warning(
            "Duplicate client-wide default rate resolved for client_id=%s: "
            "kept rate #%s (most recently updated), removed %s",
            client_id, keep_id, remove_ids,
        )
        for remove_id in remove_ids:
            bind.execute(sa.text("DELETE FROM client_product_rates WHERE id = :rid"), {"rid": remove_id})

    if not index_exists(bind, "client_product_rates", INDEX_NAME):
        bind.execute(sa.text(
            f"CREATE UNIQUE INDEX {INDEX_NAME} ON client_product_rates (client_id) WHERE product_id IS NULL"
        ))


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="client_product_rates")
