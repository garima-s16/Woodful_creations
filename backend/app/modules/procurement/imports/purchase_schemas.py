from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class ImportRowPreview(BaseModel):
    row_number: int
    material_name: Optional[str] = None
    specification: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    supplier_name: Optional[str] = None
    rate: Optional[Decimal] = None
    gst_percent: Optional[Decimal] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    remarks: Optional[str] = None
    matched_material_id: Optional[int] = None
    matched_supplier_id: Optional[int] = None
    is_new_material: bool = False
    errors: List[str] = []


class ImportPreviewResponse(BaseModel):
    total_rows: int
    matched_rows: int
    new_material_rows: int
    error_rows: int
    rows: List[ImportRowPreview]


class ImportCommitRow(BaseModel):
    """What the frontend sends back after the user reviews the preview -
    each row echoes the parsed values plus the user's decision for any
    unmatched material (create it, or skip this row)."""
    material_name: Optional[str] = None
    specification: Optional[str] = None
    quantity: Decimal
    unit: str
    matched_material_id: Optional[int] = None
    matched_supplier_id: int
    rate: Decimal
    gst_percent: Decimal = Decimal("0")
    invoice_date: Optional[datetime] = None
    remarks: Optional[str] = None
    create_new_material: bool = False

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("rate")
    @classmethod
    def rate_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Rate cannot be negative")
        return v

    @field_validator("gst_percent")
    @classmethod
    def gst_percent_in_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("GST percent must be between 0 and 100")
        return v


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    created_materials: int
    created_purchases: int
    purchase_ids: List[int]
    error: Optional[str] = None
