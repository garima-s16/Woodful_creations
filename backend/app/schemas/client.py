from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClientBase(BaseModel):
    client_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    status: str = "Active"
    lead_source: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    lead_source: Optional[str] = None
    remarks: Optional[str] = None


class ClientResponse(ClientBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientWithStats(ClientResponse):
    total_orders: int
    total_sales: Optional[float] = None
