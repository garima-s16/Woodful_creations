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
    status = Column(String(20), nullable=False, default="Applied", index=True)  # Applied/Shortlisted/Selected/Rejected
    remarks = Column(Text, nullable=True)

    interviews = relationship("Interview", back_populates="candidate")
