from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

class OrderExpenseBase(BaseModel):
    category: str
    amount: Decimal
    description: Optional[str] = None

class OrderExpenseCreate(OrderExpenseBase):
    remarks: Optional[str] = None

class OrderExpenseResponse(OrderExpenseBase):
    id: int
    order_id: int
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    order_id: str
    client_id: int
    project_type: str
    order_value: Decimal
    status: str = "Enquiry"

class OrderCreate(OrderBase):
    delivery_date: Optional[date] = None
    advance_payment: Optional[Decimal] = 0
    priority: Optional[str] = None
    lead_source: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None

class OrderUpdate(BaseModel):
    project_type: Optional[str] = None
    order_value: Optional[Decimal] = None
    status: Optional[str] = None
    delivery_date: Optional[date] = None
    advance_payment: Optional[Decimal] = None
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None

class OrderProfitability(BaseModel):
    order_id: str
    order_value: Decimal
    total_received: Decimal
    pending_payment: Decimal
    total_expenses: Decimal
    gross_profit: Decimal
    margin_percent: float

class OrderResponse(OrderBase):
    id: int
    delivery_date: Optional[date]
    advance_payment: Decimal
    priority: Optional[str]
    lead_source: Optional[str]
    supervisor: Optional[str]
    site_address: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
