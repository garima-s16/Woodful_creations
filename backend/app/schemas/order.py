from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

# Reuses the same category vocabulary as estimate line items, since an
# order's items are frequently copied straight from an estimate's.
LINE_ITEM_CATEGORIES = [
    "Material", "Labor", "Furniture", "Hardware", "Installation", "Transportation", "Design", "Service", "Other",
]


class OrderItemBase(BaseModel):
    description: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")
    # Optional link to the Product Master - identifies exactly what was
    # ordered, when it corresponds to a real catalog/custom product.
    product_id: Optional[int] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is None or v == "":
            return v
        if v not in LINE_ITEM_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(LINE_ITEM_CATEGORIES)}")
        return v


class OrderItemCreate(OrderItemBase):
    # Product ID is mandatory for every NORMAL order line item (Family
    # 102 Product ID requirement) - see the matching estimate schema
    # for why this stays Optional[int] at the type level, and for
    # is_custom_item (spec section 15's one-off-request escape hatch).
    product_id: Optional[int] = None
    is_custom_item: bool = False

    @model_validator(mode="after")
    def product_id_required_unless_custom(self):
        if not self.is_custom_item and self.product_id is None:
            raise ValueError("Product ID is required")
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
    # see app/utils/client_matching.py) must be supplied - never both
    # left unset. Exactly one path is validated in OrderCreate below.
    client_id: Optional[int] = None
    project_type: Optional[str] = None
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: Decimal = Decimal("0")
    # Discount is an absolute amount (same meaning as Estimate.discount,
    # not a percentage - see app/utils/calculations.py). order_value is
    # server-computed as items_subtotal - discount + tax_amount; a
    # caller-supplied order_value is only used as a fallback when there
    # are no line items at all (a bare order with just a total).
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None

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


class OrderCreate(OrderBase):
    advance: Decimal = Decimal("0")
    items: List[OrderItemCreate] = []
    # When set, the new order's items are copied from that estimate's
    # line items (not re-entered by hand), and the estimate is linked
    # back to the new order. Not a stored column on Order itself - it's
    # only used at creation time to drive the copy.
    from_estimate_id: Optional[int] = None

    # Client recognition intake (see app/utils/client_matching.py):
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
    # Traceability back to the estimate this order was converted from
    # (Family 102 section 6/10: "the source Estimate must remain
    # traceable"). None for an order created directly, not from an
    # estimate. Derived from the existing Order.estimates relationship
    # (the FK actually lives on Estimate.order_id) - not a stored
    # column, so this can never drift out of sync with the real link.
    source_estimate_id: Optional[int] = None
    source_estimate_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
