"""Recruitment domain schemas - candidates and their interviews.
Consolidated from separate candidate.py/interview.py modules: the two
are tightly coupled (an interview always references a candidate) and
together form one small, coherent "recruitment" feature area, not two
independent concerns."""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re

# --- Candidate ---------------------------------------------------------

EXPERIENCE_OPTIONS = ["Fresher", "< 1 year", "1-2 years", "2-5 years", "5-10 years", "10+ years"]
INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9][0-9]{9}$")


class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    # Backward-compatible free-text URL (e.g. a LinkedIn/portfolio link);
    # the actual uploaded file is tracked separately via
    # resume_stored_filename/resume_original_filename, set only through
    # the dedicated upload endpoint, never through this create/update body.
    resume_url: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_indian_mobile(cls, v):
        if v is None or v == "":
            return v
        if not INDIAN_MOBILE_PATTERN.match(v):
            raise ValueError("Mobile number must be a valid 10-digit Indian number (starting 6-9)")
        return v

    @field_validator("experience")
    @classmethod
    def validate_experience_option(cls, v):
        if v is None or v == "":
            return v
        if v not in EXPERIENCE_OPTIONS:
            raise ValueError(f"Experience must be one of: {', '.join(EXPERIENCE_OPTIONS)}")
        return v


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    status: Optional[str] = None
    remarks: Optional[str] = None


class CandidateResponse(CandidateBase):
    id: int
    business_id: str
    status: str
    resume_original_filename: Optional[str] = None
    resume_content_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Interview -----------------------------------------------------------

RECOMMENDATION_OPTIONS = ["Strong Hire", "Hire", "Hold", "Reject"]


class InterviewBase(BaseModel):
    candidate_id: int
    round: Optional[str] = None
    scheduled_date: datetime
    interviewer: Optional[str] = None


class InterviewCreate(InterviewBase):
    pass


class InterviewFeedbackFields(BaseModel):
    """Shared by InterviewUpdate (feedback is entered via the same
    update endpoint as scheduling changes - there's one interview
    record, not a separate feedback resource) and validated the same
    way wherever it's set."""
    overall_rating: Optional[int] = None
    technical_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    culture_fit_rating: Optional[int] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    observations: Optional[str] = None
    recommendation: Optional[str] = None

    @field_validator("overall_rating", "technical_rating", "communication_rating", "culture_fit_rating")
    @classmethod
    def validate_rating_range(cls, v):
        if v is None:
            return v
        if not (1 <= v <= 5):
            raise ValueError("Ratings must be between 1 and 5")
        return v

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v):
        if v is None or v == "":
            return v
        if v not in RECOMMENDATION_OPTIONS:
            raise ValueError(f"Recommendation must be one of: {', '.join(RECOMMENDATION_OPTIONS)}")
        return v


class InterviewUpdate(InterviewFeedbackFields):
    status: Optional[str] = None
    feedback: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class InterviewResponse(InterviewBase, InterviewFeedbackFields):
    id: int
    business_id: str
    status: str
    feedback: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
