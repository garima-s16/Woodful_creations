from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class SupplierMaterialCreate(BaseModel):
    supplier_id: int
    material_id: int
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: bool = False
    notes: Optional[str] = None


class SupplierMaterialUpdate(BaseModel):
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None


class SupplierMaterialResponse(BaseModel):
    id: int
    supplier_id: int
    material_id: int
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    last_purchase_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierMaterialWithSupplierName(SupplierMaterialResponse):
    """Used when listing a material's suppliers - the supplier's name is
    what the UI actually needs to display, not just its ID."""
    supplier_name: str


class SupplierMaterialWithMaterialName(SupplierMaterialResponse):
    """Used when listing a supplier's materials."""
    material_name: str
