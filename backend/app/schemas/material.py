from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class MaterialBase(BaseModel):
    material_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    category: Optional[str] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: str
    minimum_stock: int = 0
    average_rate: Decimal = Decimal("0")
    supplier_id: Optional[int] = None
    location: Optional[str] = None


class MaterialCreate(MaterialBase):
    opening_stock: int = 0


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[int] = None
    average_rate: Optional[Decimal] = None
    supplier_id: Optional[int] = None
    location: Optional[str] = None


class MaterialResponse(MaterialBase):
    id: int
    business_id: Optional[str] = None
    opening_stock: int
    total_purchased: int
    total_issued: int
    current_stock: int
    stock_status: str
    stock_value: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
