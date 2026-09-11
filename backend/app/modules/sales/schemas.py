"""Sales domain Pydantic schemas."""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from app.modules.sales.models import Estimate, EstimateLineItem, Order, OrderItem, OrderComment, Payment, PaymentDocument, WHOLE_NUMBER_UNITS, quantity_violates_whole_unit_rule, LINE_ITEM_CATEGORIES, ORDER_PRIORITIES, PAYMENT_TYPES


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
    # see app/modules/clients/services.py) must be supplied - never both
    # left unset. Exactly one path is validated in OrderCreate below.
    client_id: Optional[int] = None
    project_type: Optional[str] = None
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: Decimal = Decimal("0")
    # Discount is an absolute amount (same meaning as Estimate.discount,
    # not a percentage - see app/modules/sales/services.py's compute_totals function). order_value is
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

    # Client recognition intake (see app/modules/clients/services.py):
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
    # Balance-Before-Dispatch guardrail (Family 137, feature 4): only
    # read when this call is setting delivery_status to "Completed" on
    # an order with a nonzero balance. False/omitted means the guardrail
    # applies normally; True requires override_reason to be a non-empty
    # string, and both are written to the audit trail alongside the
    # override - see sales/api.py update_order.
    override_balance_guardrail: Optional[bool] = False
    override_reason: Optional[str] = None

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


# ============================================================
# Family 137, feature 8 - Approved Specification / Sample Lock
# ============================================================

class ApprovedSpecificationCreate(BaseModel):
    """What staff records at the moment a client approves a physical or
    digital sample. approved_by is who on the client side approved it
    (not the staff member submitting this - that's the logged-in user,
    captured server-side). All spec fields are optional individually
    since a given approval may only concern e.g. a finish, not every
    attribute - but at least one should realistically be set."""
    material: Optional[str] = None
    finish: Optional[str] = None
    veneer: Optional[str] = None
    laminate: Optional[str] = None
    colour: Optional[str] = None
    hardware: Optional[str] = None
    batch_reference: Optional[str] = None
    sample_photo_path: Optional[str] = None
    notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    @model_validator(mode="after")
    def require_at_least_one_spec_field(self):
        spec_fields = (self.material, self.finish, self.veneer, self.laminate,
                       self.colour, self.hardware, self.batch_reference)
        if not any(f and str(f).strip() for f in spec_fields):
            raise ValueError(
                "At least one specification field (material, finish, veneer, "
                "laminate, colour, hardware, or batch_reference) is required."
            )
        return self


class ApprovedSpecificationResponse(BaseModel):
    id: int
    order_id: int
    version: int
    supersedes_id: Optional[int] = None
    material: Optional[str] = None
    finish: Optional[str] = None
    veneer: Optional[str] = None
    laminate: Optional[str] = None
    colour: Optional[str] = None
    hardware: Optional[str] = None
    batch_reference: Optional[str] = None
    sample_photo_path: Optional[str] = None
    notes: Optional[str] = None
    status: str
    approved_by: Optional[str] = None
    approved_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Family 137, feature 9 - Cost-Drift Alert
# ============================================================

class DeliveryPromiseRecord(BaseModel):
    """Family 137 feature 12 - the human's final delivery-date decision
    (POST /api/orders/{id}/delivery-promise). promised_date is the one
    the salesperson/owner actually selected, which may or may not match
    any of the system's suggested alternatives - the system recommends,
    it never picks for them."""
    promised_date: datetime
    reason: Optional[str] = None


class CostDriftLineItem(BaseModel):
    """Per-line drift detail - only meaningful for a line item that has
    both a product_id (so "current cost" can be looked up) and a
    recorded cost_at_creation (so "original cost" is actually known,
    not guessed). A line item missing either is left out of the drifted
    list entirely rather than reported with a fabricated number."""
    line_item_id: int
    description: str
    original_cost: Decimal
    current_cost: Decimal
    cost_delta: Decimal
    rate: Decimal  # the quoted selling rate - held constant to show margin impact
    original_margin_percent: Optional[Decimal] = None
    current_margin_percent: Optional[Decimal] = None


class CostDriftResponse(BaseModel):
    estimate_id: int
    estimate_code: str
    quote_age_days: int
    checked_line_items: int
    drifted_line_items: int
    skipped_line_items: int  # no product_id and/or no cost_at_creation recorded - genuinely unknown, not zero drift
    original_cost_total: Decimal
    current_cost_total: Decimal
    cost_delta_total: Decimal
    original_margin_percent: Optional[Decimal] = None
    current_margin_percent: Optional[Decimal] = None
    items: List[CostDriftLineItem]


# ============================================================
# Family 137, feature 6 - Smart Estimate / Margin Optimization
# ============================================================

class MarginOptimizationRequest(BaseModel):
    """What the salesperson supplies when a client pushes back on
    price - at least one of these two should be set, or there is
    nothing to optimize toward."""
    target_price: Optional[Decimal] = None
    min_margin_percent: Optional[Decimal] = None

    @model_validator(mode="after")
    def require_a_target(self):
        if self.target_price is None and self.min_margin_percent is None:
            raise ValueError("Provide a target_price and/or a min_margin_percent to optimize toward.")
        return self


class MarginOptimizationSuggestion(BaseModel):
    """One candidate substitution for one line item - a like-for-like
    swap to a different catalog product in the same category, never a
    generic discount. Nothing here is applied automatically; the human
    picks a suggestion and edits the estimate's line items themselves
    through the normal update-estimate flow."""
    line_item_id: int
    current_description: str
    current_product_id: Optional[int] = None
    current_rate: Decimal
    quantity: Decimal
    suggested_product_id: int
    suggested_product_name: str
    suggested_rate: Decimal
    saving_per_unit: Decimal
    total_saving: Decimal
    resulting_margin_percent: Optional[Decimal] = None
    availability_note: str


class MarginOptimizationResponse(BaseModel):
    estimate_id: int
    estimate_code: str
    current_total: Decimal
    current_margin_percent: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    min_margin_percent: Optional[Decimal] = None
    best_achievable_price: Decimal  # current_total minus every suggested saving, if all were applied
    target_reachable: Optional[bool] = None  # None when no target_price was given to check against
    suggestions: List[MarginOptimizationSuggestion]
