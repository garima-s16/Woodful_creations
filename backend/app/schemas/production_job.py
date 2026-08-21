from pydantic import BaseModel
from typing import Optional
from datetime import datetime, time


class ProductionJobBase(BaseModel):
    job_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    machine: Optional[str] = None
    employee_id: Optional[int] = None
    order_id: Optional[int] = None
    operation: Optional[str] = None
    stage: Optional[str] = None
    material_id: Optional[int] = None
    planned_qty: int = 0
    completed_qty: int = 0
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: str = "Not Started"
    remarks: Optional[str] = None
    blocker_reason: Optional[str] = None


class ProductionJobCreate(ProductionJobBase):
    pass


class ProductionJobUpdate(BaseModel):
    completed_qty: Optional[int] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    remarks: Optional[str] = None
    blocker_reason: Optional[str] = None


class ProductionJobResponse(ProductionJobBase):
    id: int
    business_id: Optional[str] = None
    completion_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
