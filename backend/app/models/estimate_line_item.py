from sqlalchemy import Column, String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class EstimateLineItem(BaseModel):
    """A single priced item within an estimate - e.g. "Wardrobe",
    "Hardware", "Installation". Real per-item quantity/rate/amount, not a
    single flat material+labor figure - so an estimate can actually
    itemize what a client is being quoted for, not just a total."""
    __tablename__ = "estimate_line_items"

    estimate_id = Column(Integer, ForeignKey("estimates.id"), nullable=False, index=True)
    # Family 21 - same optional Product link as OrderItem.product_id;
    # when an order is created from this estimate, the link is copied
    # forward onto the new OrderItem (see _build_order_items in
    # api/routes/orders.py) so the Product trail survives the
    # estimate -> order conversion.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # Material/Labor/Hardware/Installation/Transportation/Design/...
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, stored (not computed at read time)
    sort_order = Column(Integer, nullable=False, default=0)

    estimate = relationship("Estimate", back_populates="line_items")
    product = relationship("Product", back_populates="estimate_line_items")

    @property
    def product_name(self):
        return self.product.name if self.product else None
