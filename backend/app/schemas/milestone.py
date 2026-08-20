from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MilestoneBase(BaseModel):
    order_id: int
    name: str
    target_date: Optional[datetime] = None
    remarks: Optional[str] = None


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    target_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    remarks: Optional[str] = None


class MilestoneResponse(MilestoneBase):
    id: int
    business_id: Optional[str] = None
    completed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
