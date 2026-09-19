"""Add two indexes for frequently-executed, previously-unindexed query
patterns identified during the page-load performance hardening pass.

Both are declared at the ORM level too (Order.delivery_date's Column,
and Notification's __table_args__) so a fresh Base.metadata.create_all()
/ test database gets them for free - same "model declares it, this
migration is what an existing already-provisioned database needs"
split every other index in this chain (see 0078) already follows.

1. orders.delivery_date - the dashboard's "upcoming deliveries" widget
   (app/modules/reporting/pages/DashboardPage.jsx's secondary-data
   load -> GET /api/orders/?upcoming_delivery_within_days=14) runs a
   direct range filter on this column on every dashboard load, for
   every user, and it previously had no index of its own to support
   that filter (only order_date and project_status were indexed).

2. notifications(recipient_user_id, is_read) - unread_count()
   (app/modules/communications/api.py) is polled every 60 seconds by
   every logged-in user's NotificationBell, making it the single most
   frequently executed query against this table. It always filters on
   both columns together; each already had its own single-column
   index, so this composite lets that hot path resolve as one index
   seek instead of intersecting two separate scans.

Both use create_index_if_missing() (app.platform.database), matching
every other migration in this chain, so re-running this migration or
running it against a database that already has either index for some
other reason is a safe no-op rather than an error.

Forward-only in the sense that downgrade() simply drops both indexes -
there is no data-reconciliation step here (unlike 0078), so this is
safe to reverse; downgrade is still implemented for completeness.
"""
from alembic import op
from app.platform.database import create_index_if_missing, index_exists


revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_index_if_missing(
        bind, "ix_orders_delivery_date", "orders", ["delivery_date"],
    )
    create_index_if_missing(
        bind, "ix_notifications_recipient_unread", "notifications",
        ["recipient_user_id", "is_read"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "orders", "ix_orders_delivery_date"):
        op.drop_index("ix_orders_delivery_date", table_name="orders")
    if index_exists(bind, "notifications", "ix_notifications_recipient_unread"):
        op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
