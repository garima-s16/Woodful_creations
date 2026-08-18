from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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
