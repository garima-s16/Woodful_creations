from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class CandidateBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    position: str
    experience: str

class CandidateCreate(CandidateBase):
    resume_url: Optional[str] = None

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    resume_url: Optional[str] = None
    status: Optional[str] = None

class CandidateResponse(CandidateBase):
    id: int
    resume_url: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True