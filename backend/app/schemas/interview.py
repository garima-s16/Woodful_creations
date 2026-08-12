from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

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
