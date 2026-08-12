from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

LINE_ITEM_CATEGORIES = [
    "Material", "Labor", "Furniture", "Hardware", "Installation", "Transportation", "Design", "Service", "Other",
]


class EstimateLineItemBase(BaseModel):
    description: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is None or v == "":
            return v
        if v not in LINE_ITEM_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(LINE_ITEM_CATEGORIES)}")
        return v


class EstimateLineItemCreate(EstimateLineItemBase):
    pass


class EstimateLineItemResponse(EstimateLineItemBase):
    id: int
    estimate_id: int
    amount: Decimal
    sort_order: int

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


class EstimateUpdate(BaseModel):
    material_cost: Optional[Decimal] = None
    labor_cost: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    status: Optional[str] = None
    valid_until: Optional[datetime] = None
    remarks: Optional[str] = None
    line_items: Optional[List[EstimateLineItemCreate]] = None


class EstimateResponse(EstimateBase):
    id: int
    business_id: Optional[str] = None
    subtotal: Decimal
    tax_amount: Decimal
    total_cost: Decimal
    status: str
    version: int
    parent_estimate_id: Optional[int]
    line_items: List[EstimateLineItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
