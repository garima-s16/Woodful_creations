from pydantic import BaseModel, field_validator
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
    # Family 21 - Product <-> Order Item relationship. Optional: a
    # genuinely custom, one-off order line can still have no Product
    # Master entry. When set on create, description/unit/rate are
    # server-defaulted from the Product's own catalog values if the
    # caller left them blank - see _build_order_items() in
    # api/routes/orders.py.
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
    pass


class OrderItemResponse(OrderItemBase):
    id: int
    order_id: int
    amount: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    source_estimate_item_id: Optional[int] = None
    sort_order: int
    product_name: Optional[str] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    order_code: Optional[str] = None  # server-generated on create, ignored if supplied
    client_id: int
    project_type: Optional[str] = None
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: Decimal = Decimal("0")
    priority: Optional[str] = None
    supervisor: Optional[str] = None
    site_address: Optional[str] = None
    remarks: Optional[str] = None


class OrderCreate(OrderBase):
    advance: Decimal = Decimal("0")
    items: List[OrderItemCreate] = []
    # When set, the new order's items are copied from that estimate's
    # line items (not re-entered by hand), and the estimate is linked
    # back to the new order. Not a stored column on Order itself - it's
    # only used at creation time to drive the copy.
    from_estimate_id: Optional[int] = None


class OrderUpdate(BaseModel):
    project_type: Optional[str] = None
    delivery_date: Optional[datetime] = None
    order_value: Optional[Decimal] = None
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


class OrderResponse(OrderBase):
    id: int
    business_id: Optional[str] = None
    order_value: Optional[Decimal] = None
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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
