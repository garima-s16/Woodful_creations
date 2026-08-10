from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    material_type: str
    thickness: float
    category: str
    description: Optional[str] = None
    quantity: int
    min_quantity: int = 10
    price_per_unit: Decimal
    unit: str = "sheets"
    sku: Optional[str] = None
    supplier: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    material_type: Optional[str] = None
    thickness: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    min_quantity: Optional[int] = None
    price_per_unit: Optional[Decimal] = None
    unit: Optional[str] = None
    sku: Optional[str] = None
    supplier: Optional[str] = None
    last_restocked: Optional[datetime] = None

class ProductResponse(ProductBase):
    id: int
    last_restocked: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True