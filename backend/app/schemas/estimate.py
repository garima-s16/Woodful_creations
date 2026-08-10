from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EstimateBase(BaseModel):
    client_id: int
    client_name: str
    description: str
    material_cost: Decimal
    labor_cost: Decimal

class EstimateCreate(EstimateBase):
    pass

class EstimateUpdate(BaseModel):
    client_name: Optional[str] = None
    description: Optional[str] = None
    material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    status: Optional[str] = None

class EstimateResponse(EstimateBase):
    id: int
    total_cost: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True