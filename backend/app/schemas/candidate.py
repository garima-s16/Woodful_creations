from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


EXPERIENCE_OPTIONS = ["Fresher", "< 1 year", "1-2 years", "2-5 years", "5-10 years", "10+ years"]


class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    resume_url: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_indian_mobile(cls, v):
        if v is None or v == "":
            return v
        if not v.isdigit() or len(v) != 10:
            raise ValueError("Mobile number must be exactly 10 digits")
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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
