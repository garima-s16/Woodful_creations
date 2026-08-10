from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class EstimateBase(BaseModel):
    estimate_code: str
    client_id: int
    order_id: Optional[int] = None
    description: Optional[str] = None
    material_cost: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    valid_until: Optional[datetime] = None
    remarks: Optional[str] = None


class EstimateCreate(EstimateBase):
    pass


class EstimateUpdate(BaseModel):
    material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    status: Optional[str] = None
    valid_until: Optional[datetime] = None
    remarks: Optional[str] = None


class EstimateResponse(EstimateBase):
    id: int
    tax_amount: Decimal
    total_cost: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
