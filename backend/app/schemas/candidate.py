from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    resume_url: Optional[str] = None
    remarks: Optional[str] = None


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    status: Optional[str] = None
    remarks: Optional[str] = None


class CandidateResponse(CandidateBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
