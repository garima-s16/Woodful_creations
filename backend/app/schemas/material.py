from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from app.schemas.material_category import MaterialAttributeValueInput, MaterialAttributeValueResponse


class MaterialBase(BaseModel):
    material_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    # Kept for backward compatibility - existing consumers read this
    # directly. When subcategory_id is set, this is derived server-side
    # from the subcategory's category name, not taken from client input.
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: str
    minimum_stock: int = 0
    average_rate: Decimal = Decimal("0")
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None


class MaterialCreate(MaterialBase):
    opening_stock: int = 0
    attribute_values: List[MaterialAttributeValueInput] = []


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[int] = None
    average_rate: Optional[Decimal] = None
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None
    attribute_values: Optional[List[MaterialAttributeValueInput]] = None


class MaterialResponse(MaterialBase):
    id: int
    business_id: Optional[str] = None
    opening_stock: int
    total_purchased: int
    total_issued: int
    current_stock: int
    stock_status: str
    stock_value: float
    attribute_values: List[MaterialAttributeValueResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
