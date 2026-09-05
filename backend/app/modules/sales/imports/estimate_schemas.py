from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class EstimateImportItemPreview(BaseModel):
    row_number: int
    estimate_ref: Optional[int] = None
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    rate: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    errors: List[str] = []


class EstimateImportHeaderPreview(BaseModel):
    row_number: int
    estimate_ref: Optional[int] = None
    raw_estimate_id: Optional[str] = None
    matched_estimate_id: Optional[int] = None
    matched_estimate_code: Optional[str] = None
    is_new_estimate: bool = True
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    matched_client_id: Optional[int] = None
    estimate_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    margin_percent: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    notes: Optional[str] = None
    errors: List[str] = []
    # Items that reference this header's row number, already validated.
    items: List[EstimateImportItemPreview] = []
    computed_subtotal: Optional[Decimal] = None
    computed_tax_amount: Optional[Decimal] = None
    computed_total: Optional[Decimal] = None


class EstimateImportPreviewResponse(BaseModel):
    total_estimates: int
    valid_estimates: int
    error_estimates: int
    new_estimates: int
    existing_estimates: int
    orphan_item_rows: List[EstimateImportItemPreview] = []  # items whose Estimate Row # matches no header row
    estimates: List[EstimateImportHeaderPreview]


class EstimateImportCommitItem(BaseModel):
    product_id: int
    description: str
    category: Optional[str] = None
    quantity: Decimal
    unit: str = "Nos"
    rate: Decimal
    discount_percent: Decimal = Decimal("0")
    tax_percent: Optional[Decimal] = None

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

    @field_validator("discount_percent")
    @classmethod
    def discount_percent_in_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("Discount percent must be between 0 and 100")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_in_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Tax percent must be between 0 and 100")
        return v


class EstimateImportCommitEstimate(BaseModel):
    """Echoes one reviewed header row back for actual creation/update."""
    matched_estimate_id: Optional[int] = None  # None = create new
    client_id: int
    estimate_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    margin_percent: Optional[Decimal] = None
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    notes: Optional[str] = None
    items: List[EstimateImportCommitItem]
    skip: bool = False

    @field_validator("discount")
    @classmethod
    def discount_must_not_be_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Discount cannot be negative.")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_must_be_valid(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("Tax percent must be between 0 and 100.")
        return v


class EstimateImportCommitRequest(BaseModel):
    estimates: List[EstimateImportCommitEstimate]


class EstimateImportCommitResultRow(BaseModel):
    estimate_id: Optional[int] = None
    estimate_code: Optional[str] = None
    created: bool = False
    updated: bool = False
    skipped: bool = False
    error: Optional[str] = None


class EstimateImportCommitResult(BaseModel):
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    results: List[EstimateImportCommitResultRow]
