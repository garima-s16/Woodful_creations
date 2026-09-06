"""Sales domain schemas - estimates, orders, and payments. Consolidated
from three separate modules: genuinely tightly coupled (an order can be
converted from an estimate and copies its line items; a payment always
references an order), not three independent concerns.

estimate_import.py and order_import.py are deliberately NOT included
here - they're bulk-import infrastructure, a different concern from
this module's core CRUD schemas."""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.modules.sales.quantity_rules import WHOLE_NUMBER_UNITS, quantity_violates_whole_unit_rule  # noqa: F401 - re-exported for existing importers

# Shared by both estimate and order line items - an order's items are
# frequently copied straight from an estimate's, so both use the same
# category vocabulary.
LINE_ITEM_CATEGORIES = [
    "Material", "Labor", "Furniture", "Hardware", "Installation", "Transportation", "Design", "Service", "Other",
]

# The real, existing Order priority vocabulary (confirmed against
# OrdersPage.jsx's PRIORITY_OPTIONS dropdown, not invented here) -
# previously defined nowhere in the backend, so an arbitrary string
# could be set via direct API call, Excel import, or chat despite the
# UI only ever offering these four. Deliberately NOT the same set as
# DailyTask's own priority vocabulary (Low/Normal/High/Urgent, see
# app/modules/operations/schemas.py) - these are two separate fields on
# two separate entities with two separate, independently-established
# real dropdowns; unifying them would be a product decision this
# schema fix should not make on its own.
ORDER_PRIORITIES = {"Low", "Medium", "High", "Urgent"}


# --- Estimate -----------------------------------------------------------


class EstimateLineItemBase(BaseModel):
    description: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    # Optional link to the Product Master - what was actually quoted,
    # when it corresponds to a real catalog/custom product.
    product_id: Optional[int] = None


class EstimateLineItemCreate(EstimateLineItemBase):
    # Product ID is mandatory for every NORMAL estimate line item -
    # kept Optional[int] at the
    # type level so a custom validator can raise the exact required
    # message below, rather than Pydantic's generic "field required"
    # text. Existence/active-status validation happens in the route
    # (needs a DB session) - see _build_line_items in estimates.py.
    #
    # is_custom_item is the deliberate escape hatch:
    # a genuine one-off customer request ("add brass inlay to the
    # table") that doesn't exist in Product Master and shouldn't be
    # forced into it - when True, product_id is not required.
    product_id: Optional[int] = None
    is_custom_item: bool = False

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is None or v == "":
            return v
        if v not in LINE_ITEM_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(LINE_ITEM_CATEGORIES)}")
        return v

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


# --- Order -----------------------------------------------------------


class OrderItemBase(BaseModel):
    description: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    # Optional link to the Product Master - identifies exactly what was
    # ordered, when it corresponds to a real catalog/custom product.
    product_id: Optional[int] = None


class OrderItemCreate(OrderItemBase):
    # Product ID is mandatory for every NORMAL order line item -
    # see the matching estimate schema
    # for why this stays Optional[int] at the type level, and for
    # is_custom_item (the one-off-request escape hatch).
    product_id: Optional[int] = None
    is_custom_item: bool = False

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is None or v == "":
            return v
        if v not in LINE_ITEM_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(LINE_ITEM_CATEGORIES)}")
        return v

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


class OrderItemResponse(OrderItemBase):
    id: int
    order_id: int
    amount: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    source_estimate_item_id: Optional[int] = None
    sort_order: int
    product_name: Optional[str] = None
    product_code: Optional[str] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    order_code: Optional[str] = None  # server-generated on create, ignored if supplied
    # Either client_id (an already-selected/known client) OR
    # client_name + client_phone (quick order-intake recognition flow,
    # see app/modules/clients/matching.py) must be supplied - never both
    # left unset. Exactly one path is validated in OrderCreate below.
    client_id: Optional[int] = None
    project_type: Optional[str] = None
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: Decimal = Decimal("0")
    # Discount is an absolute amount (same meaning as Estimate.discount,
    # not a percentage - see app/modules/sales/calculations.py). order_value is
    # server-computed as items_subtotal - discount + tax_amount; a
    # caller-supplied order_value is only used as a fallback when there
    # are no line items at all (a bare order with just a total).
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None


class OrderCreate(OrderBase):
    @field_validator("discount")
    @classmethod
    def discount_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError("Discount cannot be negative.")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_must_be_valid(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Tax percent must be between 0 and 100.")
        return v

    @field_validator("order_value")
    @classmethod
    def order_value_must_not_be_negative(cls, v):
        if v < 0:
            raise ValueError("Order value cannot be negative.")
        return v

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v):
        if v is None or v == "":
            return v
        v = v.strip()
        if v not in ORDER_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(ORDER_PRIORITIES))}")
        return v

    advance: Decimal = Decimal("0")
    items: List[OrderItemCreate] = []
    # When set, the new order's items are copied from that estimate's
    # line items (not re-entered by hand), and the estimate is linked
    # back to the new order. Not a stored column on Order itself - it's
    # only used at creation time to drive the copy.
    from_estimate_id: Optional[int] = None

    # Client recognition intake (see app/modules/clients/matching.py):
    # name AND phone must BOTH match an existing client for that client
    # to be reused; otherwise a new client is created. Only used when
    # client_id is not supplied.
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    # Only applied if a *new* client ends up being created via
    # client_name/client_phone - never overwrites an existing client's
    # stored details.
    client_email: Optional[str] = None
    client_contact_person: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_lead_source: Optional[str] = None

    @model_validator(mode="after")
    def require_client_identification(self):
        if self.client_id is not None:
            return self
        if self.client_name and self.client_phone:
            return self
        raise ValueError(
            "Provide either client_id, or both client_name and client_phone to identify the client for this order."
        )


class OrderUpdate(BaseModel):
    project_type: Optional[str] = None
    delivery_date: Optional[datetime] = None
    order_value: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    project_status: Optional[str] = None
    design_status: Optional[str] = None
    execution_status: Optional[str] = None
    delivery_status: Optional[str] = None
    progress_percent: Optional[int] = None
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None
    items: Optional[List[OrderItemCreate]] = None

    @field_validator("discount")
    @classmethod
    def discount_must_not_be_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Discount cannot be negative.")
        return v

    @field_validator("tax_percent")
    @classmethod
    def tax_percent_must_be_valid(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Tax percent must be between 0 and 100.")
        return v

    @field_validator("progress_percent")
    @classmethod
    def progress_percent_must_be_valid(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Progress percent must be between 0 and 100.")
        return v

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v):
        if v is None or v == "":
            return v
        v = v.strip()
        if v not in ORDER_PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(sorted(ORDER_PRIORITIES))}")
        return v


class OrderResponse(OrderBase):
    id: int
    business_id: Optional[str] = None
    order_value: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    advance: Optional[Decimal] = None
    other_received: Optional[Decimal] = None
    total_received: Optional[Decimal] = None
    balance: Optional[Decimal] = None
    items_subtotal: Optional[Decimal] = None
    payment_status: Optional[str] = None
    project_status: str
    design_status: str
    execution_status: str
    delivery_status: str
    progress_percent: int
    items: List[OrderItemResponse] = []
    # Traceability back to the estimate this order was converted from -
    # None for an order created directly, not from an estimate. Derived
    # from the existing Order.estimates relationship (the FK actually
    # lives on Estimate.order_id) - not a stored column, so this can
    # never drift out of sync with the real link.
    source_estimate_id: Optional[int] = None
    source_estimate_code: Optional[str] = None
    # Family 130 P0.1 s.11: a lightweight, batched, non-material
    # attention flag - never computed in React, never a fabricated
    # score. Set by _serialize_orders from OrderService.bulk_attention_flags
    # (blocked/overdue tasks, production blockers, delivery risk only -
    # material-shortage risk is the business-wide dashboard's separate,
    # heavier BOM/stock calculation and is deliberately NOT duplicated
    # here on every list page load). None for any order not looked at
    # by that bulk pass (there is none today - kept Optional for schema
    # safety only).
    needs_attention: Optional[bool] = None
    attention_reason: Optional[str] = None
    attention_risk_level: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderCommentCreate(BaseModel):
    text: str


class OrderCommentResponse(BaseModel):
    id: int
    order_id: int
    author: str
    text: str
    date: datetime

    class Config:
        from_attributes = True


# --- Payment -----------------------------------------------------------

# The real, consistent vocabulary confirmed against both frontend
# pages that create a payment (OrderDetailPage.jsx, PaymentsPage.jsx) -
# both agree on these exact 3 values.
#
# payment_mode is deliberately NOT enumerated here - this app's own
# CASH_MODES constant (app/modules/sales/order_service.py) already documents
# payment_mode as free-text, and the two frontend pages currently offer
# genuinely different, unreconciled option lists for it (e.g. "Bank" vs
# "Bank Transfer", "Credit Card" vs "Card"/"Cheque"/"Other"). Enforcing
# either list alone would reject legitimate submissions from whichever
# page doesn't match - reconciling that is a frontend UI change, out of
# scope for this pass.
PAYMENT_TYPES = ("Advance", "Progress Payment", "Internal")


class PaymentBase(BaseModel):
    receipt_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    order_id: int
    payment_type: str
    payment_mode: str
    amount: Decimal
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None


class PaymentCreate(PaymentBase):
    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v

    @field_validator("payment_type")
    @classmethod
    def payment_type_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PAYMENT_TYPES:
            raise ValueError(f"Payment Type must be one of: {', '.join(PAYMENT_TYPES)}")
        return v


class PaymentUpdate(BaseModel):
    payment_type: Optional[str] = None
    payment_mode: Optional[str] = None
    amount: Optional[Decimal] = None
    reference_number: Optional[str] = None
    received_by: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class PaymentResponse(PaymentBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentDocumentResponse(BaseModel):
    id: int
    payment_id: int
    original_filename: str
    content_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
