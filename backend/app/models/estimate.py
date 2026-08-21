from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from decimal import Decimal
from app.models.base import BaseModel


class Estimate(BaseModel):
    """Cost estimate for a client/order - material + labor cost, tax,
    total. Independent of Order.order_value so a client can be quoted
    before an order is confirmed."""
    __tablename__ = "estimates"

    estimate_code = Column(String(20), unique=True, nullable=False, index=True)  # EST-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # estimate_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    # material_cost/labor_cost remain for backward compatibility with
    # estimates created before line items existed - a new estimate with
    # real line items drives its totals from the sum of those instead
    # (see subtotal property below).
    material_cost = Column(Numeric(12, 2), nullable=False, default=0)
    labor_cost = Column(Numeric(12, 2), nullable=False, default=0)
    discount = Column(Numeric(12, 2), nullable=False, default=0)
    tax_percent = Column(Numeric(5, 2), nullable=False, default=18)
    # Estimate-specific margin override (pricing priority level 4, see
    # app/utils/pricing_priority.py) - applies to this estimate's line
    # items that don't have a more specific override (explicit
    # line-item price or customer-specific pricing), without touching
    # any Product's own global margin_percent.
    margin_percent_override = Column(Numeric(5, 2), nullable=True)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_cost = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft", index=True)  # draft/sent/approved/rejected
    valid_until = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    # Versioning: revising an estimate creates a new row rather than
    # overwriting history. version 1 has parent_estimate_id = None; every
    # revision points back to the same root via parent_estimate_id.
    version = Column(Integer, nullable=False, default=1)
    parent_estimate_id = Column(Integer, ForeignKey("estimates.id"), nullable=True, index=True)

    client = relationship("Client")
    order = relationship("Order", back_populates="estimates")
    parent_estimate = relationship("Estimate", remote_side="Estimate.id", backref="revisions")
    line_items = relationship("EstimateLineItem", back_populates="estimate",
                               cascade="all, delete-orphan", order_by="EstimateLineItem.sort_order")

    @property
    def subtotal(self):
        """Sum of line item amounts if any exist; falls back to the legacy
        material_cost + labor_cost for estimates created before line
        items existed, so old records still compute a correct total."""
        if self.line_items:
            return sum((item.amount or Decimal("0") for item in self.line_items), Decimal("0"))
        return (self.material_cost or Decimal("0")) + (self.labor_cost or Decimal("0"))
