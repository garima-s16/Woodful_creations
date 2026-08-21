from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class PaymentBase(BaseModel):
    receipt_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    order_id: int
    payment_type: str
    payment_mode: str
    amount: Decimal
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    payment_type: Optional[str] = None
    payment_mode: Optional[str] = None
    amount: Optional[Decimal] = None
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None


class PaymentResponse(PaymentBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
