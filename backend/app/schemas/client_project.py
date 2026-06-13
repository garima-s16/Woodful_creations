from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ClientProjectBase(BaseModel):
    client_id: int
    project_name: str
    description: Optional[str] = None
    cost: float

class ClientProjectCreate(ClientProjectBase):
    pass

class ClientProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    design_status: Optional[str] = None
    execution_status: Optional[str] = None
    delivery_status: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    cost: Optional[float] = None
    amount_paid: Optional[float] = None
    amount_pending: Optional[float] = None

class ClientProjectResponse(ClientProjectBase):
    id: int
    design_status: str
    execution_status: str
    delivery_status: str
    amount_paid: float
    amount_pending: float
    estimated_delivery: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True