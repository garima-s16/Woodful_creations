from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class ProductMaterialInput(BaseModel):
    material_id: int
    quantity_required: Decimal = Decimal("1")
    unit: Optional[str] = None
    notes: Optional[str] = None


class ProductMaterialResponse(ProductMaterialInput):
    id: int
    material_name: Optional[str] = None

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    product_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    product_type: str = "standard"  # "standard" | "custom"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    specifications: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = "in"
    primary_material: Optional[str] = None
    finish: Optional[str] = None
    unit: str = "Nos"
    gst_percent: Optional[Decimal] = Decimal("18")
    material_cost: Optional[Decimal] = None
    hardware_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    machine_cost: Optional[Decimal] = None
    finish_cost: Optional[Decimal] = None
    packing_cost: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    other_cost: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    materials_used: List[ProductMaterialInput] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    product_type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    specifications: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = None
    primary_material: Optional[str] = None
    finish: Optional[str] = None
    unit: Optional[str] = None
    gst_percent: Optional[Decimal] = None
    material_cost: Optional[Decimal] = None
    hardware_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    machine_cost: Optional[Decimal] = None
    finish_cost: Optional[Decimal] = None
    packing_cost: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    other_cost: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    materials_used: Optional[List[ProductMaterialInput]] = None


class ProductResponse(ProductBase):
    id: int
    business_id: Optional[str] = None
    suggested_cost_price: Optional[float] = None
    suggested_selling_price: Optional[float] = None
    margin: Optional[float] = None
    actual_margin_percent: Optional[float] = None
    materials_used: List[ProductMaterialResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
