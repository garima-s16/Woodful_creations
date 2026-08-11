from pydantic import BaseModel
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


class SupplierResponse(SupplierBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
