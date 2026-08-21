from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class PersonalCartItemCreate(BaseModel):
    material_id: int
    quantity: Decimal = Decimal("1")
    supplier_id: Optional[int] = None
    note: Optional[str] = None


class PersonalCartItemUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    note: Optional[str] = None


class PersonalCartItemResponse(BaseModel):
    id: int
    material_id: int
    material_name: str
    unit: Optional[str] = None
    quantity: Decimal
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    rate: Optional[Decimal] = None
    note: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
