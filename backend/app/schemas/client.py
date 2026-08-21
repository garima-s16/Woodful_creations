from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

from app.utils.validators import validate_phone, validate_email


class ClientBase(BaseModel):
    client_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    contact_person: Optional[str] = None
    alternate_phone: Optional[str] = None
    # Mandatory (Client Master section 3) - a confirmed demo-testing
    # finding. Must be EXACTLY 10 digits - no country code, no
    # separators. Every rejection reason (missing, wrong length,
    # non-numeric, formatted) uses the exact same message, by explicit
    # requirement: "Please enter valid mobile number".
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    gstin: Optional[str] = None
    status: str = "Active"
    lead_source: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and not validate_email(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    gstin: Optional[str] = None
    status: Optional[str] = None
    lead_source: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # Phone is mandatory on the entity - an update is allowed to
        # leave it unset (unchanged), but never to explicitly clear it
        # to empty, and any value supplied must still be exactly 10
        # digits. Same exact message for every rejection reason.
        if v is None:
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and not validate_email(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class ClientResponse(ClientBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientWithStats(ClientResponse):
    total_orders: int
    total_sales: Optional[float] = None
