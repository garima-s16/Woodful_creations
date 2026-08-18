from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class PurchaseBase(BaseModel):
    purchase_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    supplier_id: int
    material_id: int
    quantity: Decimal
    unit: str
    rate: Decimal
    gst_percent: Decimal = Decimal("0")
    payment_status: str = "Paid"
    receipt_status: str = "Received"  # "Ordered" = not yet received, stock untouched until marked received


class PurchaseCreate(PurchaseBase):
    """taxable_value, gst_amount, invoice_total are computed server-side
    from quantity * rate and gst_percent - never trust client-sent totals."""
    pass


class PurchaseUpdate(BaseModel):
    payment_status: Optional[str] = None


class PurchaseResponse(PurchaseBase):
    id: int
    business_id: Optional[str] = None
    taxable_value: Decimal
    gst_amount: Decimal
    invoice_total: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
