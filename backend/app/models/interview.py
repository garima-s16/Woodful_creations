from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Interview(BaseModel):
    __tablename__ = "interviews"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    round = Column(String(50), nullable=True)
    scheduled_date = Column(DateTime, nullable=False, index=True)
    interviewer = Column(String(255), nullable=True)
    feedback = Column(Text, nullable=True)  # free-form notes, kept alongside the structured fields below
    status = Column(String(20), nullable=False, default="Scheduled", index=True)  # Scheduled/Completed/Rescheduled/Cancelled

    # Structured feedback (P8) - was a single free-text box; a real
    # hiring decision needs more than one paragraph to be useful to
    # whoever reads it later.
    overall_rating = Column(Integer, nullable=True)  # 1-5
    technical_rating = Column(Integer, nullable=True)  # 1-5
    communication_rating = Column(Integer, nullable=True)  # 1-5
    culture_fit_rating = Column(Integer, nullable=True)  # 1-5
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)
    recommendation = Column(String(20), nullable=True)  # Strong Hire/Hire/Hold/Reject

    candidate = relationship("Candidate", back_populates="interviews")
