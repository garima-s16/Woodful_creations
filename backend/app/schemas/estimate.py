from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EstimateBase(BaseModel):
    client_id: int
    client_name: str
    description: str
    material_cost: float
    labor_cost: float

class EstimateCreate(EstimateBase):
    pass

class EstimateUpdate(BaseModel):
    client_name: Optional[str] = None
    description: Optional[str] = None
    material_cost: Optional[float] = None
    labor_cost: Optional[float] = None
    status: Optional[str] = None

class EstimateResponse(EstimateBase):
    id: int
    total_cost: float
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True