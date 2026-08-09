from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class PurchaseOrderBase(BaseModel):
    purchase_id: str
    supplier_id: int
    material_id: int
    quantity: int
    unit: str
    rate: Decimal

class PurchaseOrderCreate(PurchaseOrderBase):
    gst_percent: Optional[Decimal] = Decimal("18.00")
    remarks: Optional[str] = None

class PurchaseOrderUpdate(BaseModel):
    quantity: Optional[int] = None
    rate: Optional[Decimal] = None
    gst_percent: Optional[Decimal] = None
    payment_status: Optional[str] = None
    remarks: Optional[str] = None

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    date: datetime
    taxable_value: Decimal
    gst_amount: Decimal
    invoice_total: Decimal
    payment_status: str
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
