"""Procurement domain Pydantic schemas."""
from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime
from app.modules.procurement.models import Supplier, SupplierMaterial, Purchase, ProcurementRequirement, SupplierDecision, PersonalCartItem, PROCUREMENT_REQUIREMENT_STATUSES
from app.modules.inventory.models import PURCHASE_CREATE_RECEIPT_STATUSES


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


class ProcurementRequirementCreate(BaseModel):
    """required_quantity/available_quantity_at_creation/
    shortage_quantity_at_creation are deliberately NOT accepted here -
    the route always derives them itself from
    StockService.calculate_order_material_requirements at creation
    time, the one authoritative shortage calculation, never a
    client-supplied number."""
    order_id: int
    material_id: int
    priority: Optional[str] = None
    required_by_date: Optional[datetime] = None
    remarks: Optional[str] = None


class ProcurementRequirementUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    required_by_date: Optional[datetime] = None
    remarks: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in PROCUREMENT_REQUIREMENT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(PROCUREMENT_REQUIREMENT_STATUSES))}")
        return v


class SupplierDecisionCreate(BaseModel):
    """recommended_supplier_id/recommended_reason are deliberately NOT
    accepted here either - the route derives them itself from
    ProcurementService._supplier_options_for_materials at decision time, a
    frozen snapshot of what was actually recommended, never a
    client-supplied value that could misrepresent the recommendation."""
    requirement_id: int
    selected_supplier_id: int
    decision_reason: Optional[str] = None


class SupplierDecisionResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    requirement_id: int
    recommended_supplier_id: Optional[int] = None
    recommended_supplier_name: Optional[str] = None
    recommended_reason: Optional[str] = None
    selected_supplier_id: int
    selected_supplier_name: Optional[str] = None
    decision_reason: Optional[str] = None
    decided_by: Optional[str] = None
    followed_recommendation: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProcurementRequirementResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    order_id: Optional[int] = None
    material_id: int
    material_name: Optional[str] = None
    required_quantity: Decimal
    available_quantity_at_creation: Decimal
    shortage_quantity_at_creation: Decimal
    status: str
    priority: Optional[str] = None
    required_by_date: Optional[datetime] = None
    purchase_id: Optional[int] = None
    remarks: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    decision: Optional[SupplierDecisionResponse] = None

    class Config:
        from_attributes = True


class RequirementPurchaseCreate(BaseModel):
    """Creates the Purchase for an already-decided ProcurementRequirement.
    supplier_id/material_id are deliberately NOT accepted here - they
    come from the requirement itself and its recorded SupplierDecision,
    never re-typed by the client, so the resulting Purchase can never
    disagree with the decision that was actually made."""
    quantity: Decimal
    unit: str
    rate: Decimal
    gst_percent: Decimal = Decimal("0")
    expected_delivery_date: Optional[datetime] = None
    receipt_status: str = "Ordered"
    location_id: Optional[int] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("rate")
    @classmethod
    def rate_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Rate cannot be negative")
        return v

    @field_validator("receipt_status")
    @classmethod
    def receipt_status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PURCHASE_CREATE_RECEIPT_STATUSES:
            raise ValueError(f"Receipt Status must be one of: {', '.join(sorted(PURCHASE_CREATE_RECEIPT_STATUSES))}")
        return v
