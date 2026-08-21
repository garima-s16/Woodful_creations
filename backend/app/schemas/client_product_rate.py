from pydantic import BaseModel, model_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ClientProductRateBase(BaseModel):
    client_id: int
    product_id: Optional[int] = None  # None = client-wide default margin, applies to every product for this client
    margin_percent: Optional[Decimal] = None
    fixed_selling_price: Optional[Decimal] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def exactly_one_override_type(self):
        # "Do not silently combine conflicting overrides" - a customer
        # override is either a margin adjustment or a direct negotiated
        # price, never presented as both at once.
        if self.margin_percent is not None and self.fixed_selling_price is not None:
            raise ValueError("Set either margin_percent or fixed_selling_price, not both.")
        if self.margin_percent is None and self.fixed_selling_price is None:
            raise ValueError("Set either margin_percent or fixed_selling_price.")
        if self.margin_percent is not None and self.margin_percent >= 100:
            raise ValueError("Margin percent must be less than 100%.")
        return self


class ClientProductRateCreate(ClientProductRateBase):
    pass


class ClientProductRateUpdate(BaseModel):
    margin_percent: Optional[Decimal] = None
    fixed_selling_price: Optional[Decimal] = None
    notes: Optional[str] = None


class ClientProductRateResponse(ClientProductRateBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PricingResolveRequest(BaseModel):
    """Preview what rate would apply, and which rule would win, before
    actually saving a line item - lets the Estimate UI show "Calculated
    Price" vs "Manually Overridden Price" clearly, per spec section 12."""
    product_id: Optional[int] = None
    client_id: Optional[int] = None
    estimate_id: Optional[int] = None
    explicit_override: Optional[Decimal] = None


class PricingResolveResponse(BaseModel):
    selling_rate: Decimal
    pricing_rule_applied: str
    margin_percent_used: Optional[Decimal] = None
    cost_used: Optional[Decimal] = None
