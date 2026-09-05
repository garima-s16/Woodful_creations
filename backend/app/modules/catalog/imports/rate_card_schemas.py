from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal

from app.modules.catalog.models import uom_allowed_for_category
from app.modules.catalog.schemas import (
    _validate_uom, _validate_source_type, _validate_confidence,
    _validate_margin_under_100, _validate_rate_field_not_negative,
)


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

    # Reuses the exact same rules RateCardCreate enforces (see
    # app/schemas/rate_card.py) - the import commit path must not be
    # able to create a rate card the normal API would reject.
    @field_validator("uom")
    @classmethod
    def uom_must_be_standard(cls, v):
        return _validate_uom(v)

    @model_validator(mode="after")
    def uom_must_suit_category(self):
        if self.category and self.uom and not uom_allowed_for_category(self.category, self.uom):
            raise ValueError(f"'{self.uom}' is not an appropriate unit for category '{self.category}'.")
        return self

    @field_validator("source_type")
    @classmethod
    def source_type_must_be_known(cls, v):
        return _validate_source_type(v)

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_known(cls, v):
        return _validate_confidence(v)

    @field_validator("target_margin_percent")
    @classmethod
    def margin_must_be_under_100(cls, v):
        return _validate_margin_under_100(v)

    @field_validator("market_reference_rate", "woodful_cost_rate", "woodful_selling_rate",
                      "overhead_percent", "wastage_percent", "tax_percent")
    @classmethod
    def rate_fields_not_negative(cls, v):
        return _validate_rate_field_not_negative(v)


class RateCardImportCommitRequest(BaseModel):
    rows: List[RateCardImportCommitRow]


class RateCardImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    rate_ids: List[int]
    error: Optional[str] = None
