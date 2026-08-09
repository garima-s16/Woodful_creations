from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MaterialBase(BaseModel):
    material_id: str
    name: str
    category: str
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: str
    minimum_stock: int = 10

class MaterialCreate(MaterialBase):
    opening_stock: int = 0

class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[int] = None
    is_active: Optional[int] = None

class MaterialResponse(MaterialBase):
    id: int
    opening_stock: int
    total_purchased: int
    total_issued: int
    current_stock: int
    is_active: int
    stock_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
