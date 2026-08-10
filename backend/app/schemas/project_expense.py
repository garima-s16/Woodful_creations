from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ProjectExpenseBase(BaseModel):
    expense_code: str
    date: datetime
    order_id: int
    category: str
    description: Optional[str] = None
    paid_to: Optional[str] = None
    amount: Decimal
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class ProjectExpenseCreate(ProjectExpenseBase):
    pass


class ProjectExpenseUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    paid_to: Optional[str] = None
    amount: Optional[Decimal] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class ProjectExpenseResponse(ProjectExpenseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
