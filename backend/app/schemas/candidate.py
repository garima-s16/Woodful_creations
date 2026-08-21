from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re

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
