from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InterviewBase(BaseModel):
    candidate_id: int
    round: str
    scheduled_date: datetime
    interviewer: str

class InterviewCreate(InterviewBase):
    feedback: Optional[str] = None

class InterviewUpdate(BaseModel):
    scheduled_date: Optional[datetime] = None
    interviewer: Optional[str] = None
    feedback: Optional[str] = None
    status: Optional[str] = None

class InterviewResponse(InterviewBase):
    id: int
    feedback: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True