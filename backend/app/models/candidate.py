from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Candidate(BaseModel):
    __tablename__ = "candidates"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    position = Column(String(100), nullable=True)
    experience = Column(String(100), nullable=True)
    resume_url = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="Applied", index=True)  # Applied/Shortlisted/Selected/Rejected
    remarks = Column(Text, nullable=True)

    interviews = relationship("Interview", back_populates="candidate")
