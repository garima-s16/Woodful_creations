from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AttendanceBase(BaseModel):
    employee_id: int
    attendance_date: datetime
    status: str = "present"

class AttendanceCreate(AttendanceBase):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None

class AttendanceUpdate(BaseModel):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    hours_worked: Optional[float] = None
    status: Optional[str] = None

class AttendanceResponse(AttendanceBase):
    id: int
    check_in: Optional[datetime]
    check_out: Optional[datetime]
    hours_worked: float
    created_at: datetime

    class Config:
        from_attributes = True