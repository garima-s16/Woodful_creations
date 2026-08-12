from pydantic import BaseModel
from typing import Optional
from datetime import datetime, time


class DailyTaskBase(BaseModel):
    task_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    employee_id: int
    order_id: Optional[int] = None
    task_description: str
    priority: Optional[str] = None
    planned_start: Optional[time] = None
    planned_end: Optional[time] = None
    status: str = "Not Started"
    completion_percent: int = 0
    checked_by: Optional[str] = None
    delay_reason: Optional[str] = None
    remarks: Optional[str] = None


class DailyTaskCreate(DailyTaskBase):
    pass


class DailyTaskUpdate(BaseModel):
    status: Optional[str] = None
    completion_percent: Optional[int] = None
    checked_by: Optional[str] = None
    delay_reason: Optional[str] = None
    remarks: Optional[str] = None


class DailyTaskResponse(DailyTaskBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
