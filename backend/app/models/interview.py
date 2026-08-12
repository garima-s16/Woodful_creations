from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Interview(BaseModel):
    __tablename__ = "interviews"

    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    round = Column(String(50), nullable=True)
    scheduled_date = Column(DateTime, nullable=False, index=True)
    interviewer = Column(String(255), nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="Scheduled", index=True)  # Scheduled/Completed/Rescheduled/Cancelled

    candidate = relationship("Candidate", back_populates="interviews")
