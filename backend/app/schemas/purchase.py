from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class PurchaseBase(BaseModel):
    purchase_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    expected_delivery_date: Optional[datetime] = None
    supplier_id: int
    material_id: int
    quantity: Decimal
    unit: str
    rate: Decimal
    gst_percent: Decimal = Decimal("0")
    payment_status: str = "Paid"
    receipt_status: str = "Received"  # "Ordered" = not yet received, stock untouched until marked received
    location_id: Optional[int] = None  # which location receives the stock; falls back to the material's primary location if omitted


class PurchaseCreate(PurchaseBase):
    """taxable_value, gst_amount, invoice_total are computed server-side
    from quantity * rate and gst_percent - never trust client-sent totals."""
    pass


class PurchaseUpdate(BaseModel):
    payment_status: Optional[str] = None


class PurchaseReceiveRequest(BaseModel):
    """Optional - if quantity is omitted, receives everything still
    outstanding (the original all-or-nothing behavior)."""
    quantity: Optional[Decimal] = None
    location_id: Optional[int] = None  # which location receives this delivery; falls back to the purchase's own location_id, then the material's primary location


class PurchaseResponse(PurchaseBase):
    id: int
    business_id: Optional[str] = None
    taxable_value: Decimal
    gst_amount: Decimal
    invoice_total: Decimal
    quantity_received: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
