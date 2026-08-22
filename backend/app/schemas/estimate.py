from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.utils.quantity_rules import WHOLE_NUMBER_UNITS, quantity_violates_whole_unit_rule  # noqa: F401 - re-exported for existing importers

LINE_ITEM_CATEGORIES = [
    "Material", "Labor", "Furniture", "Hardware", "Installation", "Transportation", "Design", "Service", "Other",
]


class EstimateLineItemBase(BaseModel):
    description: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    # Optional link to the Product Master - what was actually quoted,
    # when it corresponds to a real catalog/custom product.
    product_id: Optional[int] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is None or v == "":
            return v
        if v not in LINE_ITEM_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(LINE_ITEM_CATEGORIES)}")
        return v


class EstimateLineItemCreate(EstimateLineItemBase):
    # Product ID is mandatory for every NORMAL estimate line item
    # (Family 102 Product ID requirement) - kept Optional[int] at the
    # type level so a custom validator can raise the exact required
    # message below, rather than Pydantic's generic "field required"
    # text. Existence/active-status validation happens in the route
    # (needs a DB session) - see _build_line_items in estimates.py.
    #
    # is_custom_item (spec section 15) is the deliberate escape hatch:
    # a genuine one-off customer request ("add brass inlay to the
    # table") that doesn't exist in Product Master and shouldn't be
    # forced into it - when True, product_id is not required.
    product_id: Optional[int] = None
    is_custom_item: bool = False

    @model_validator(mode="after")
    def product_id_required_unless_custom(self):
        if not self.is_custom_item and self.product_id is None:
            raise ValueError("Product ID is required")
        return self

    @model_validator(mode="after")
    def quantity_must_be_whole_for_countable_units(self):
        if quantity_violates_whole_unit_rule(self.quantity, self.unit):
            raise ValueError(f"{self.unit} must be a whole number, not a fractional quantity.")
        return self

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return v

    @field_validator("rate")
    @classmethod
    def rate_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError("Rate cannot be negative.")
        return v


class EstimateLineItemResponse(EstimateLineItemBase):
    id: int
    estimate_id: int
    amount: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    sort_order: int
    product_name: Optional[str] = None
    product_code: Optional[str] = None

    class Config:
        from_attributes = True


class EstimateBase(BaseModel):
    estimate_code: Optional[str] = None  # server-generated on create, ignored if supplied
    client_id: int
    order_id: Optional[int] = None
    description: Optional[str] = None
    # Kept for backward compatibility with estimates created before line
    # items existed. A new estimate should normally be created via
    # line_items instead - when line_items is provided, these two are
    # ignored as calculation inputs (subtotal is derived from the items).
    material_cost: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    valid_until: Optional[datetime] = None
    remarks: Optional[str] = None


class EstimateCreate(EstimateBase):
    line_items: List[EstimateLineItemCreate] = []

    @field_validator("material_cost", "labor_cost", "discount")
    @classmethod
    def amount_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError("Amount cannot be negative.")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_must_be_valid(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Tax percent must be between 0 and 100.")
        return v


class EstimateUpdate(BaseModel):
    material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    status: Optional[str] = None
    valid_until: Optional[datetime] = None
    remarks: Optional[str] = None
    line_items: Optional[List[EstimateLineItemCreate]] = None

    @field_validator("material_cost", "labor_cost", "discount")
    @classmethod
    def amount_must_not_be_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Amount cannot be negative.")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_must_be_valid(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Tax percent must be between 0 and 100.")
        return v


class EstimateResponse(EstimateBase):
    id: int
    business_id: Optional[str] = None
    material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    status: str
    version: int
    parent_estimate_id: Optional[int]
    line_items: List[EstimateLineItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
