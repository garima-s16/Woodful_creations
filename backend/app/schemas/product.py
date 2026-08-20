from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.models.product import PRODUCT_TYPES

DIMENSION_UNITS = ["in", "cm", "ft", "mm"]


class ProductMaterialInput(BaseModel):
    """What the frontend sends when setting a product's bill of
    materials - keyed by material_id, matching the same "submit the
    current complete list" semantics MaterialAttributeValueInput
    already uses for material attributes."""
    material_id: int
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None


class ProductMaterialResponse(BaseModel):
    id: int
    material_id: int
    material_name: str
    material_unit: str
    quantity: Decimal
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    product_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    sku: Optional[str] = None
    product_type: str = "standard"
    # Kept for backward compatibility, same sync pattern as Material.category -
    # when subcategory_id is set, this is derived server-side, not taken
    # from client input.
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    description: Optional[str] = None
    specifications: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: str = "in"
    finish: Optional[str] = None
    unit: str = "Piece"
    notes: Optional[str] = None
    is_active: bool = True
    cost_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    lead_time_days: Optional[int] = None

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v):
        if v not in PRODUCT_TYPES:
            raise ValueError(f"product_type must be one of: {', '.join(PRODUCT_TYPES)}")
        return v

    @field_validator("dimension_unit")
    @classmethod
    def validate_dimension_unit(cls, v):
        if v not in DIMENSION_UNITS:
            raise ValueError(f"dimension_unit must be one of: {', '.join(DIMENSION_UNITS)}")
        return v


class ProductCreate(ProductBase):
    bom_items: List[ProductMaterialInput] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    product_type: Optional[str] = None
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    description: Optional[str] = None
    specifications: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = None
    finish: Optional[str] = None
    unit: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    bom_items: Optional[List[ProductMaterialInput]] = None

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v):
        if v is not None and v not in PRODUCT_TYPES:
            raise ValueError(f"product_type must be one of: {', '.join(PRODUCT_TYPES)}")
        return v

    @field_validator("dimension_unit")
    @classmethod
    def validate_dimension_unit(cls, v):
        if v is not None and v not in DIMENSION_UNITS:
            raise ValueError(f"dimension_unit must be one of: {', '.join(DIMENSION_UNITS)}")
        return v


class ProductResponse(ProductBase):
    id: int
    business_id: Optional[str] = None
    # Optional, not the base Decimal - redacted (set to None server-side)
    # for non-master roles, same discipline as Material.average_rate -
    # see _serialize_products() in api/routes/products.py.
    cost_price: Optional[Decimal] = None
    margin: Optional[float] = None
    bom_items: List[ProductMaterialResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
