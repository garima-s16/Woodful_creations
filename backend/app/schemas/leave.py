from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class LeaveBase(BaseModel):
    employee_id: int
    leave_type: str
    start_date: datetime
    end_date: datetime
    days: Decimal = Decimal("1")
    reason: Optional[str] = None


class LeaveCreate(LeaveBase):
    pass


class LeaveUpdate(BaseModel):
    status: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class LeaveResponse(LeaveBase):
    id: int
    status: str
    approved_by: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
