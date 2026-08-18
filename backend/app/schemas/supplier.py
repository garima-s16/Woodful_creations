from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class SupplierBase(BaseModel):
    supplier_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    category: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    payment_terms: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    payment_terms: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class SupplierResponse(SupplierBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
