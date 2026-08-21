from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class LeaveBase(BaseModel):
    employee_id: int
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None


class LeaveCreate(LeaveBase):
    """`days` is deliberately NOT accepted from the client - it is always
    computed server-side (inclusive calendar-day count) in the leaves route,
    so a bad frontend calculation (or a tampered request) can never produce
    a 0/negative/NaN value in the database."""
    pass


class LeaveUpdate(BaseModel):
    status: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class LeaveResponse(LeaveBase):
    id: int
    business_id: str
    days: Decimal
    status: str
    approved_by: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
