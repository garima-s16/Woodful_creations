from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.platform.database import BaseModel
from typing import List, Optional
from datetime import datetime


class Notification(BaseModel):
    """A real notification generated from an actual business event
    (low stock crossed, a purchase received, a payment overdue, ...) -
    never fabricated or created just to populate the UI.

    related_entity_type/related_entity_id is one generic pair, not a
    dedicated field per entity type - the same pattern already used for
    ChatContext.record_type/record_id, for the same reason (Material,
    Order, Purchase, Project... adding a new notifiable entity type
    should never require a schema change).

    dedup_key is what prevents the same situation from spamming a new
    notification every time its generator runs (e.g. on every dashboard
    load) - before creating one, the service checks for an existing
    UNREAD notification with the same key and skips creating a duplicate
    if found. Cleared naturally once the notification is read/resolved,
    since resolved notifications no longer block a fresh one when the
    same situation recurs later.

    Defect repair (F138 P9.1): the "check for an existing unread row,
    then insert if none found" description above is, on its own, a
    classic SELECT-then-INSERT race - two concurrent requests (e.g. two
    dashboard loads, or the on-demand check racing the background
    scheduler) can both see "no existing row" and both insert, creating
    two live notifications for the same situation. The partial unique
    index below closes that race at the database level: it is
    impossible for two UNREAD rows to ever share a dedup_key, no matter
    how the check-then-insert in NotificationService.notify() is timed.
    Scoped to is_read=false (not a plain unique constraint on dedup_key)
    because that matches the actual dedup rule - a READ notification
    must never block a fresh one for the same situation recurring
    later. See NotificationService.notify() for the atomic
    insert/IntegrityError-catch that relies on this index.

    NOTE for the migrations owner: this index is declared here (so a
    fresh `Base.metadata.create_all()`/test database gets it for free)
    but an EXISTING database needs a real Alembic migration to add it -
    model changes alone never alter an already-provisioned schema. The
    exact migration needed:
        op.create_index(
            "ix_notifications_dedup_key_unread", "notifications", ["dedup_key"],
            unique=True, postgresql_where=sa.text("is_read = false AND dedup_key IS NOT NULL"),
            sqlite_where=sa.text("is_read = 0 AND dedup_key IS NOT NULL"),
        )
    using the idempotent create_index_if_missing() guard from
    app/platform/database.py (migration_guards) rather than a bare
    op.create_index, exactly like every other index this project adds
    in a migration. Before adding it, any pre-existing duplicate
    UNREAD rows sharing a dedup_key (possible today, since nothing
    currently prevents them) must be reconciled - e.g. keep the
    newest per dedup_key and mark the rest is_read=true - or the
    CREATE UNIQUE INDEX itself will fail against real data."""
    __tablename__ = "notifications"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    notification_type = Column(String(30), nullable=False, index=True)
    severity = Column(String(10), nullable=False, default="INFO")  # INFO/SUCCESS/WARNING/CRITICAL
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)

    # Null recipient_user_id = broadcast to all master users,
    # since most operational events (low stock, overdue payment) are
    # relevant to whoever runs the business, not one specific person.
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    related_entity_type = Column(String(30), nullable=True)
    related_entity_id = Column(Integer, nullable=True)
    action_path = Column(String(255), nullable=True)  # frontend deep link, e.g. "/materials/5"
    # Defect repair (F138 P25 regression audit, item 20 - duplicate
    # indexes): this column previously also carried index=True, which -
    # on a schema built via Base.metadata.create_all() (the test
    # suite's path) - created a SECOND, plain, full-table index on this
    # same column alongside the explicit partial unique index declared
    # in __table_args__ below. Every actual query against dedup_key in
    # this codebase (NotificationService.notify/run_all_checks,
    # AutomationService's dedup lookup - see communications/services.py
    # and automation.py) always filters on is_read.is_(False) in the
    # same query, which the partial index below already covers
    # (postgresql_where/sqlite_where scoped to exactly that condition),
    # so the plain index was never doing any additional useful work -
    # only doubling the write-time index-maintenance cost of every
    # notification insert/update. Removed; the partial unique index is
    # now the single index on this column.
    dedup_key = Column(String(150), nullable=True)

    recipient = relationship("User")

    __table_args__ = (
        # Defect repair (F138 P9.1) - see the class docstring above for
        # the race this closes and the exact migration an existing
        # database still needs to actually get this index. Partial
        # (WHERE-scoped) unique index: only UNREAD rows with a non-null
        # dedup_key are constrained, matching the dedup rule exactly -
        # a read notification must never block re-creating one for the
        # same situation recurring later.
        Index(
            "ix_notifications_dedup_key_unread", "dedup_key", unique=True,
            postgresql_where=(is_read.is_(False) & dedup_key.isnot(None)),
            sqlite_where=(is_read.is_(False) & dedup_key.isnot(None)),
        ),
    )


class AutomationLog(BaseModel):
    """Audit trail for automation (EVENT -> CONDITION -> ACTION).

    Distinct from AuditLog (app/platform/audit.py): AuditLog records HTTP
    -request-driven user mutations and needs a Request to log (ip_address,
    the acting user_id) - automation runs aren't triggered by a request
    with a specific human actor, they're triggered by a business condition
    being met (a task going overdue, stock dropping below threshold, ...),
    so this has its own lightweight, request-independent columns instead
    of forcing AuditLog's shape onto a system-driven event.

    One row per action a rule actually took (or attempted) - never one row
    per condition *check*. This app has no background job scheduler (see
    NotificationService); automation rules run on-demand, the same
    established pattern, made idempotent via dedup_key exactly like
    Notification.dedup_key. AutomationService only ever writes a new row
    here when a rule's action was newly taken (a genuinely new Notification
    was created) or genuinely failed - re-running the same check while a
    prior occurrence is still open is a no-op, not a second log entry.
    """
    __tablename__ = "automation_logs"

    rule_key = Column(String(50), nullable=False, index=True)  # e.g. "task_overdue"
    trigger_event = Column(String(50), nullable=False)  # what caused this run, e.g. "on_demand_check", "scheduled_job"
    condition_summary = Column(Text, nullable=False)  # human-readable: the specific condition that was met
    action_taken = Column(String(100), nullable=False)  # e.g. "notify:TASK_OVERDUE", "recommend_purchase"
    # SUCCESS - the action (a notification) was fully carried out.
    # PROPOSED - a recommendation was surfaced but nothing was committed
    #            (e.g. recommend_purchase never creates a real Purchase).
    # FAILED - the rule raised while evaluating/acting on this record.
    status = Column(String(20), nullable=False, index=True)
    related_entity_type = Column(String(30), nullable=True)
    related_entity_id = Column(Integer, nullable=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=True)
    dedup_key = Column(String(150), nullable=True, index=True)
    # Only ever the exception's own text (e.g. "Order not found") - never
    # request/session data, credentials, or tokens; nothing in this
    # service ever handles a secret to begin with.
    error_message = Column(Text, nullable=True)

    notification = relationship("Notification")
