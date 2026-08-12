from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InterviewBase(BaseModel):
    candidate_id: int
    round: Optional[str] = None
    scheduled_date: datetime
    interviewer: Optional[str] = None


class InterviewCreate(InterviewBase):
    pass


class InterviewUpdate(BaseModel):
    status: Optional[str] = None
    feedback: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class InterviewResponse(InterviewBase):
    id: int
    status: str
    feedback: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
