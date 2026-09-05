"""Recruitment domain models: Candidate and Interview.

Consolidated from candidate.py + interview.py. Kept as a single small domain module since Interview has a hard
foreign-key dependency on Candidate and both are always used together.
"""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


class Candidate(BaseModel):
    __tablename__ = "candidates"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    position = Column(String(100), nullable=True)
    experience = Column(String(100), nullable=True)
    # Backward-compatible free-text URL, still accepted if a candidate's
    # resume genuinely lives externally (e.g. a LinkedIn/portfolio link)
    # rather than being uploaded as a file.
    resume_url = Column(String(500), nullable=True)
    # An actually-uploaded file (P7) - stored under a random server-side
    # filename (never the user-supplied one, to avoid any path/overwrite
    # risk), with the real original filename kept separately for display
    # and for the Content-Disposition header on download.
    resume_stored_filename = Column(String(255), nullable=True)
    resume_original_filename = Column(String(255), nullable=True)
    resume_content_type = Column(String(100), nullable=True)
    storage_backend = Column(String(20), nullable=False, default="local")
    drive_file_id = Column(String(255), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="Applied", index=True)  # Applied/Shortlisted/Selected/Rejected
    remarks = Column(Text, nullable=True)

    interviews = relationship("Interview", back_populates="candidate")


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
