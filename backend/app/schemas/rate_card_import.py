from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal


class RateCardImportRowPreview(BaseModel):
    row_number: int
    matched_rate_id: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    item_name: Optional[str] = None
    specification: Optional[str] = None
    location: Optional[str] = None
    uom: Optional[str] = None
    market_reference_rate: Optional[Decimal] = None
    woodful_cost_rate: Optional[Decimal] = None
    woodful_selling_rate: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    target_margin_percent: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    source_type: Optional[str] = None
    source_reference: Optional[str] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    is_update: bool = False
    errors: List[str] = []


class RateCardImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    update_rows: int
    error_rows: int
    rows: List[RateCardImportRowPreview]


class RateCardImportCommitRow(BaseModel):
    matched_rate_id: Optional[int] = None
    category: str
    subcategory: Optional[str] = None
    item_name: str
    specification: Optional[str] = None
    location: str = "Indore, Madhya Pradesh"
    uom: str
    market_reference_rate: Optional[Decimal] = None
    woodful_cost_rate: Optional[Decimal] = None
    woodful_selling_rate: Optional[Decimal] = None
    overhead_percent: Optional[Decimal] = None
    target_margin_percent: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    source_type: str
    source_reference: Optional[str] = None
    confidence: str = "NOT_VERIFIED"
    notes: Optional[str] = None
    skip: bool = False


class RateCardImportCommitRequest(BaseModel):
    rows: List[RateCardImportCommitRow]


class RateCardImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    rate_ids: List[int]
    error: Optional[str] = None
