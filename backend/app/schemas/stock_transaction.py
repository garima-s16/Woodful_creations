from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime

ADJUSTMENT_TYPES = ["Physical Count Increase", "Physical Count Decrease", "Damage", "Wastage", "Theft/Loss", "Correction"]


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
    adjusted_by: Optional[str] = None


class StockAdjustmentResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    material_id: int
    adjustment_type: str
    quantity_delta: Decimal
    stock_before: Decimal
    stock_after: Decimal
    reason: str
    adjusted_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
