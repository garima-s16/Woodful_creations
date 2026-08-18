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
    # Decimal, not int - a material measured in kg/litres/metres needs
    # real decimal precision (e.g. a 2.5 kg reorder threshold).
    minimum_stock: Decimal = Decimal("0")
    average_rate: Decimal = Decimal("0")
    is_active: bool = True
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None


class MaterialCreate(MaterialBase):
    opening_stock: Decimal = Decimal("0")
    attribute_values: List[MaterialAttributeValueInput] = []


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[Decimal] = None
    average_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None
    attribute_values: Optional[List[MaterialAttributeValueInput]] = None


class MaterialResponse(MaterialBase):
    id: int
    business_id: Optional[str] = None
    opening_stock: Decimal
    total_purchased: Decimal
    total_issued: Decimal
    current_stock: Decimal
    stock_status: str
    # Optional, not the base Decimal/float - an employee's response has
    # these set to None server-side (see materials.py's _scrub_financial_fields),
    # a genuine redaction, not a value the frontend merely chooses not to show.
    average_rate: Optional[Decimal] = None
    stock_value: Optional[float] = None
    attribute_values: List[MaterialAttributeValueResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
