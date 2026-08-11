from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Estimate(BaseModel):
    """Cost estimate for a client/order - material + labor cost, tax,
    total. Independent of Order.order_value so a client can be quoted
    before an order is confirmed."""
    __tablename__ = "estimates"

    estimate_code = Column(String(20), unique=True, nullable=False, index=True)  # EST-001
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    material_cost = Column(Numeric(12, 2), nullable=False, default=0)
    labor_cost = Column(Numeric(12, 2), nullable=False, default=0)
    tax_percent = Column(Numeric(5, 2), nullable=False, default=18)
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
