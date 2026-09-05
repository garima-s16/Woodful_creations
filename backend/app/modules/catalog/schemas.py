"""Catalog domain schemas - finished products and rate cards (the
pricing reference data products/estimates draw from). Consolidated
from two separate modules that together form Woodful's product
catalog.

personal_cart.py is deliberately NOT included here despite an earlier
grouping proposal that lumped it in - it references material_id, not
product_id, and is genuinely about material procurement (the inventory
domain), not the product catalog."""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.modules.catalog.models import RATE_SOURCE_TYPES, RATE_CONFIDENCE_LEVELS, STANDARD_UOMS, uom_allowed_for_category


# --- Product -----------------------------------------------------------


class ProductMaterialInput(BaseModel):
    material_id: int
    quantity_required: Decimal = Decimal("1")
    unit: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("quantity_required")
    @classmethod
    def quantity_required_must_be_positive(cls, v: Decimal) -> Decimal:
        # A BOM line means "this material is used to make the product" -
        # nothing in the product/BOM workflow ever consults a zero
        # quantity_required for anything, so a zero-quantity row is not
        # a real BOM entry.
        if v <= 0:
            raise ValueError("Quantity required must be greater than zero")
        return v


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

    @field_validator(
        "material_cost", "hardware_cost", "labour_cost", "machine_cost",
        "finish_cost", "packing_cost", "transport_cost", "other_cost",
        "cost_price", "selling_price",
    )
    @classmethod
    def cost_fields_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Cost/price fields cannot be negative")
        return v

    @field_validator("gst_percent")
    @classmethod
    def gst_percent_in_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("GST percent must be between 0 and 100")
        return v

    @field_validator("overhead_percent")
    @classmethod
    def overhead_percent_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Overhead percent cannot be negative")
        return v

    @field_validator("margin_percent")
    @classmethod
    def margin_percent_must_be_under_100(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        # Same convention as RateCard.target_margin_percent: margin is
        # gross margin on the selling price, so 100% implies an
        # infinite selling price and must be rejected.
        if v is not None and v >= 100:
            raise ValueError("Margin percent must be less than 100% (100% margin implies an infinite selling price).")
        return v


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

    @field_validator(
        "material_cost", "hardware_cost", "labour_cost", "machine_cost",
        "finish_cost", "packing_cost", "transport_cost", "other_cost",
        "cost_price", "selling_price",
    )
    @classmethod
    def cost_fields_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Cost/price fields cannot be negative")
        return v

    @field_validator("gst_percent")
    @classmethod
    def gst_percent_in_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("GST percent must be between 0 and 100")
        return v

    @field_validator("overhead_percent")
    @classmethod
    def overhead_percent_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Overhead percent cannot be negative")
        return v

    @field_validator("margin_percent")
    @classmethod
    def margin_percent_must_be_under_100(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v >= 100:
            raise ValueError("Margin percent must be less than 100% (100% margin implies an infinite selling price).")
        return v


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


# --- Rate Card -----------------------------------------------------------

# Shared, single source of truth for the numeric/vocabulary rules that
# apply to a rate card everywhere one can be created or changed (normal
# create, update/revision, override, import commit) - so those paths
# can never quietly disagree about what a valid rate card looks like.
def _validate_uom(v: str) -> str:
    if v not in STANDARD_UOMS:
        raise ValueError(f"'{v}' is not a standard UOM. Valid values: {', '.join(sorted(STANDARD_UOMS))}")
    return v


def _validate_source_type(v: str) -> str:
    if v not in RATE_SOURCE_TYPES:
        raise ValueError(f"'{v}' is not a recognized source type. Valid values: {', '.join(sorted(RATE_SOURCE_TYPES))}")
    return v


def _validate_confidence(v: str) -> str:
    if v not in RATE_CONFIDENCE_LEVELS:
        raise ValueError(f"'{v}' is not a recognized confidence level. Valid values: {', '.join(sorted(RATE_CONFIDENCE_LEVELS))}")
    return v


def _validate_margin_under_100(v: Optional[Decimal]) -> Optional[Decimal]:
    if v is not None and v >= 100:
        raise ValueError("Target margin must be less than 100% (100% margin implies an infinite selling price).")
    return v


def _validate_rate_field_not_negative(v: Optional[Decimal]) -> Optional[Decimal]:
    if v is not None and v < 0:
        raise ValueError("Rate/percentage fields cannot be negative.")
    return v


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
        return _validate_uom(v)

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

    @field_validator("source_type")
    @classmethod
    def source_type_must_be_known(cls, v):
        return _validate_source_type(v) if v is not None else v

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_known(cls, v):
        return _validate_confidence(v) if v is not None else v

    @field_validator("target_margin_percent")
    @classmethod
    def margin_must_be_under_100(cls, v):
        return _validate_margin_under_100(v)

    @field_validator("market_reference_rate", "woodful_cost_rate", "woodful_selling_rate",
                      "overhead_percent", "wastage_percent", "tax_percent")
    @classmethod
    def rate_fields_not_negative(cls, v):
        return _validate_rate_field_not_negative(v)


class RateCardOverride(BaseModel):
    override_price: Decimal
    override_reason: Optional[str] = None

    @field_validator("override_price")
    @classmethod
    def override_price_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Override price cannot be negative.")
        return v


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
