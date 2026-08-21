from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime

ADJUSTMENT_TYPES = [
    "Physical Count Increase", "Physical Count Decrease", "Damage", "Wastage", "Theft/Loss",
    "Correction", "Return from Issue",
]


class StockTransferCreate(BaseModel):
    material_id: int
    quantity: Decimal
    to_location_id: int
    from_location_id: Optional[int] = None
    transferred_by: Optional[str] = None
    remarks: Optional[str] = None


class StockTransferResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    material_id: int
    quantity: Decimal
    from_location_id: Optional[int] = None
    to_location_id: int
    transferred_by: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StockAdjustmentCreate(BaseModel):
    material_id: int
    adjustment_type: str
    quantity_delta: Decimal
    reason: str
    related_issue_id: Optional[int] = None
    adjusted_by: Optional[str] = None
    location_id: Optional[int] = None  # which location this adjustment applies to; falls back to the material's primary location if omitted


class StockAdjustmentResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    material_id: int
    adjustment_type: str
    quantity_delta: Decimal
    stock_before: Decimal
    stock_after: Decimal
    reason: str
    related_issue_id: Optional[int] = None
    adjusted_by: Optional[str] = None
    location_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LocationBalance(BaseModel):
    """One location's share of a material's total stock, derived from
    the ledger - never an independently stored number."""
    location_id: Optional[int] = None  # None = movements recorded before multi-location existed, with no location on the material either
    location_name: str
    quantity: Decimal


class MaterialLocationStockResponse(BaseModel):
    material_id: int
    material_name: str
    unit: str
    total: Decimal  # must always equal Material.current_stock and the sum of `locations` below
    locations: list[LocationBalance]
