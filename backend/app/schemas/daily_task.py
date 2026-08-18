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
    status: str = "TO DO"
    completion_percent: int = 0
    checked_by: Optional[str] = None
    delay_reason: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[str] = None
    parent_task_id: Optional[int] = None


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
    previous_task_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompleteAndAssignNext(BaseModel):
    """"Complete & Assign Next" - completes the current task and
    creates a new, linked one, preserving the handoff chain rather than
    overwriting the original."""
    next_employee_id: int
    next_task_description: str
    next_due_date: datetime
    next_priority: Optional[str] = None
    note: Optional[str] = None


class TaskCommentCreate(BaseModel):
    text: str


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    author: str
    text: str
    date: datetime

    class Config:
        from_attributes = True
