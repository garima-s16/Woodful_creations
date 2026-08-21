from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class ClientActivity(BaseModel):
    """A logged interaction/communication with a client - call, meeting,
    email, note, site visit, etc. Manually recorded, not auto-generated -
    this is a communication log, not an audit trail."""
    __tablename__ = "client_activities"

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    activity_type = Column(String(30), nullable=False)  # Call/Meeting/Email/Site Visit/Note
    date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    summary = Column(Text, nullable=False)
    logged_by = Column(String(255), nullable=True)
    follow_up_date = Column(DateTime, nullable=True, index=True)
    # Lets a resolved follow-up drop out of the pending-follow-ups list
    # instead of resurfacing forever. Irrelevant when follow_up_date is
    # unset (a plain note/log entry has nothing to "complete").
    follow_up_done = Column(Boolean, nullable=False, default=False)

    client = relationship("Client")
