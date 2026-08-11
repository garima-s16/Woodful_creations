from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
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

    client = relationship("Client")
