from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class IssueBase(BaseModel):
    issue_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    order_id: Optional[int] = None
    material_id: int
    quantity_issued: Decimal
    unit: str
    issued_to: Optional[str] = None
    department: Optional[str] = None
    purpose: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None
    location_id: Optional[int] = None  # which location to issue from; falls back to the material's primary location if omitted


class IssueCreate(IssueBase):
    pass


class IssueResponse(IssueBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
