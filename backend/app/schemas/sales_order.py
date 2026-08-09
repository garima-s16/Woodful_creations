from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class SalesOrderItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: int
    unit_price: float


class SalesOrderItemResponse(SalesOrderItemCreate):
    id: int
    order_id: int
    line_total: float
    created_at: datetime

    class Config:
        from_attributes = True


class SalesOrderCreate(BaseModel):
    client_name: str
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    notes: Optional[str] = None
    items: List[SalesOrderItemCreate]


class SalesOrderUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class SalesOrderResponse(BaseModel):
    id: int
    order_number: str
    client_name: str
    client_phone: Optional[str]
    client_email: Optional[str]
    status: str
    total_amount: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[SalesOrderItemResponse] = []

    class Config:
        from_attributes = True
