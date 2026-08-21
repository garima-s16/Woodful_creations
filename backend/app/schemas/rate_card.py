from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.models.rate_card import RATE_SOURCE_TYPES, RATE_CONFIDENCE_LEVELS, STANDARD_UOMS, uom_allowed_for_category


class RateCardBase(BaseModel):
    rate_code: Optional[str] = None  # server-generated, ignored if supplied
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
    tax_percent: Optional[Decimal] = Decimal("18")

    effective_from: datetime
    source_type: str
    source_reference: Optional[str] = None
    confidence: str = "NOT_VERIFIED"
    notes: Optional[str] = None

    @field_validator("uom")
    @classmethod
    def uom_must_be_standard(cls, v):
        if v not in STANDARD_UOMS:
            raise ValueError(f"'{v}' is not a standard UOM. Valid values: {', '.join(sorted(STANDARD_UOMS))}")
        return v

    @model_validator(mode="after")
    def uom_must_suit_category(self):
        # "Furniture -> Litre" is the spec's own explicit example of what
        # this must reject - Litre is a real UOM (paint/finishing), just
        # not for Furniture. Checked here (needs both fields) rather
        # than in the single-field validator above.
        if self.category and self.uom and not uom_allowed_for_category(self.category, self.uom):
            raise ValueError(f"'{self.uom}' is not an appropriate unit for category '{self.category}'.")
        return self

    @field_validator("source_type")
    @classmethod
    def source_type_must_be_known(cls, v):
        if v not in RATE_SOURCE_TYPES:
            raise ValueError(f"'{v}' is not a recognized source type. Valid values: {', '.join(sorted(RATE_SOURCE_TYPES))}")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_known(cls, v):
        if v not in RATE_CONFIDENCE_LEVELS:
            raise ValueError(f"'{v}' is not a recognized confidence level. Valid values: {', '.join(sorted(RATE_CONFIDENCE_LEVELS))}")
        return v

    @field_validator("target_margin_percent")
    @classmethod
    def margin_must_be_under_100(cls, v):
        if v is not None and v >= 100:
            raise ValueError("Target margin must be less than 100% (100% margin implies an infinite selling price).")
        return v

    @field_validator("market_reference_rate", "woodful_cost_rate", "woodful_selling_rate",
                      "overhead_percent", "wastage_percent", "tax_percent")
    @classmethod
    def rate_fields_not_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Rate/percentage fields cannot be negative.")
        return v


class RateCardCreate(RateCardBase):
    pass


class RateCardUpdate(BaseModel):
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
    effective_from: Optional[datetime] = None


class RateCardOverride(BaseModel):
    override_price: Decimal
    override_reason: Optional[str] = None


class RateCardResponse(RateCardBase):
    id: int
    business_id: Optional[str] = None
    effective_to: Optional[datetime] = None
    is_active: bool
    supersedes_id: Optional[int] = None
    override_price: Optional[Decimal] = None
    override_by: Optional[str] = None
    override_at: Optional[datetime] = None
    override_reason: Optional[str] = None
    effective_selling_rate: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
