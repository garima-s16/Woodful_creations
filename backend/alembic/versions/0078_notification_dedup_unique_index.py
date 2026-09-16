"""Close the Notification dedup race with a real partial unique index.

Defect repair (F138 P9.1). See app.modules.communications.models.Notification's
docstring for the full rationale: NotificationService.notify() does a
"SELECT for an existing unread row with this dedup_key, INSERT if none
found" check - which is a classic race between two concurrent callers
(e.g. two dashboard loads, or an on-demand check racing the background
scheduler) that can both observe "no existing row" and both insert,
producing duplicate live notifications for the same situation.

The model already declares the fix at the ORM level (a partial unique
index on dedup_key, scoped to unread rows) so a fresh
Base.metadata.create_all() / test database gets it for free - but per
the model's own docstring, that alone does nothing for an existing,
already-provisioned database. This migration is the real fix for that:

  1. Reconcile any pre-existing duplicate-unread-dedup_key rows first.
     Today nothing prevents them, so a real database may already have
     some; creating a unique index against data that violates it would
     simply fail. Reconciliation keeps the single newest row (by id,
     which is monotonically increasing and avoids any created_at
     tie-break ambiguity) per dedup_key and marks every older row with
     the same dedup_key as read (is_read=true) - matching the model
     docstring's own suggested approach. This never deletes a
     notification and never touches read ones or NULL dedup_keys; it
     only stops older duplicates from continuing to count as "unread
     and blocking" once a newer one for the same situation exists,
     which is exactly what the dedup rule intends in the no-race case
     already.
  2. Then create the partial unique index itself, via this project's
     existing create_index_if_missing() guard (app.platform.database),
     matching every other migration in this chain instead of a bare
     op.create_index - so re-running this migration, or running it
     against a database that already has the index for some other
     reason, is a safe no-op rather than an error.

Raw SQL (not the ORM) is used for the reconciliation UPDATE so this
migration has no dependency on the current shape of the Notification
model/mapper - a future column rename or model change must never be
able to silently break a historical migration.

Forward-only for the same reason as 0074-0077: reconciling pre-existing
duplicate rows is not something a downgrade could meaningfully undo
(the "which row was newest" information used to decide what to mark
is_read is not preserved anywhere a downgrade could restore from), and
dropping the index on downgrade would simply reopen the race.
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_index_if_missing


revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Step 1: reconcile pre-existing duplicate UNREAD rows sharing a
    # dedup_key, keeping only the newest (highest id) per key as
    # genuinely unread and marking the rest read. Written as one
    # portable UPDATE ... WHERE id IN (correlated subquery) rather than
    # a dialect-specific UPDATE ... FROM / JOIN, since this chain
    # targets both Postgres (production) and SQLite (tests/dev) and
    # this form runs identically on both.
    op.execute(sa.text(
        """
        UPDATE notifications
        SET is_read = true
        WHERE is_read = false
          AND dedup_key IS NOT NULL
          AND id NOT IN (
              SELECT MAX(id) FROM notifications
              WHERE is_read = false AND dedup_key IS NOT NULL
              GROUP BY dedup_key
          )
        """
    ) if dialect != "sqlite" else sa.text(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE is_read = 0
          AND dedup_key IS NOT NULL
          AND id NOT IN (
              SELECT MAX(id) FROM notifications
              WHERE is_read = 0 AND dedup_key IS NOT NULL
              GROUP BY dedup_key
          )
        """
    ))

    # Step 2: the partial unique index itself - exact specification
    # from the Notification model's docstring, created idempotently.
    create_index_if_missing(
        bind, "ix_notifications_dedup_key_unread", "notifications", ["dedup_key"],
        unique=True,
        postgresql_where=sa.text("is_read = false AND dedup_key IS NOT NULL"),
        sqlite_where=sa.text("is_read = 0 AND dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Forward-only - see module docstring."""
    raise NotImplementedError(
        "Migration 0078 is forward-only. See this module's docstring for why "
        "undoing the reconciliation step is not meaningful and dropping the "
        "index would simply reopen the dedup race."
    )
