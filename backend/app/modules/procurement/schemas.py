from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime


class PersonalCartItemCreate(BaseModel):
    material_id: int
    quantity: Decimal = Decimal("1")
    supplier_id: Optional[int] = None
    note: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class PersonalCartItemUpdate(BaseModel):
    """quantity has no lower-bound field validator here on purpose:
    the route (see update_cart_item) treats quantity <= 0 on an update
    as "remove this item from the cart", not an error - the same
    intentional behavior list_my_cart/add_to_cart never needed since
    creation has no equivalent remove semantics."""
    quantity: Optional[Decimal] = None
    note: Optional[str] = None


class PersonalCartItemResponse(BaseModel):
    id: int
    material_id: int
    material_name: str
    unit: Optional[str] = None
    quantity: Decimal
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    rate: Optional[Decimal] = None
    note: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
