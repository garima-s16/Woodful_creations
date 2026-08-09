from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class PaymentBase(BaseModel):
    receipt_id: str
    order_id: int
    client_id: int
    payment_type: str
    payment_mode: str
    amount: Decimal

class PaymentCreate(PaymentBase):
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None

class PaymentUpdate(BaseModel):
    payment_type: Optional[str] = None
    payment_mode: Optional[str] = None
    amount: Optional[Decimal] = None
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: int
    date: datetime
    reference_number: Optional[str]
    received_by: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
