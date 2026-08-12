from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class OrderBase(BaseModel):
    order_code: Optional[str] = None  # server-generated on create, ignored if supplied
    client_id: int
    project_type: Optional[str] = None
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: Decimal = Decimal("0")
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None


class OrderCreate(OrderBase):
    advance: Decimal = Decimal("0")


class OrderUpdate(BaseModel):
    project_type: Optional[str] = None
    delivery_date: Optional[datetime] = None
    order_value: Optional[Decimal] = None
    project_status: Optional[str] = None
    design_status: Optional[str] = None
    execution_status: Optional[str] = None
    delivery_status: Optional[str] = None
    progress_percent: Optional[int] = None
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None


class OrderResponse(OrderBase):
    id: int
    business_id: Optional[str] = None
    advance: Decimal
    other_received: Decimal
    total_received: Decimal
    balance: Decimal
    project_status: str
    design_status: str
    execution_status: str
    delivery_status: str
    progress_percent: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
