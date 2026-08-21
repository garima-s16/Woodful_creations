from pydantic import BaseModel
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


class ImportCommitRequest(BaseModel):
    rows: List[ImportCommitRow]


class ImportCommitResult(BaseModel):
    created_materials: int
    created_purchases: int
    purchase_ids: List[int]
    error: Optional[str] = None
