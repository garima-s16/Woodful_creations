from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


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
    same situation recurs later."""
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
    dedup_key = Column(String(150), nullable=True, index=True)

    recipient = relationship("User")


class AutomationLog(BaseModel):
    """Audit trail for automation (EVENT -> CONDITION -> ACTION).

    Distinct from AuditLog (app/platform/audit/audit.py): AuditLog records HTTP
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
