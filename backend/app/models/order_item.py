from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class OrderItem(BaseModel):
    """A single scoped item within an order - what the client actually
    ordered, not just a lump order_value. When an order is created from
    an estimate, its items are copied in from that estimate's line
    items (source_estimate_item_id records where each one came from,
    so the two stay traceable without duplicating unrelated data)."""
    __tablename__ = "order_items"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, server-computed
    source_estimate_item_id = Column(Integer, ForeignKey("estimate_line_items.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    order = relationship("Order", back_populates="items")
    source_estimate_item = relationship("EstimateLineItem")
