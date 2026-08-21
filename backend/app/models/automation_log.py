from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AutomationLog(BaseModel):
    """Audit trail for Family 13 automation (EVENT -> CONDITION -> ACTION).

    Distinct from AuditLog (app/models/audit.py): AuditLog records HTTP
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
