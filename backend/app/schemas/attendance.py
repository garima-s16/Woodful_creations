from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class AttendanceBase(BaseModel):
    date: datetime
    employee_id: int
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    standard_hours: Decimal = Decimal("8")
    attendance_status: str = "Present"
    remarks: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    attendance_status: Optional[str] = None
    remarks: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: int
    working_hours: float
    overtime_hours: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
