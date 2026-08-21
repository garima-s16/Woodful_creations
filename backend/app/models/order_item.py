from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Boolean
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
    # Optional link to the Product Master - identifies exactly what was
    # ordered, when it corresponds to a real catalog/custom product.
    # Nullable: an order item is never required to reference a product
    # (freeform lines like "Installation" stay freeform).
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    is_custom_item = Column(Boolean, nullable=False, default=False)
    pricing_rule_applied = Column(String(40), nullable=True)
    applied_margin_percent = Column(Numeric(5, 2), nullable=True)

    order = relationship("Order", back_populates="items")
    source_estimate_item = relationship("EstimateLineItem")
    product = relationship("Product", back_populates="order_items")

    @property
    def product_name(self):
        """Lets the Order Detail screen show the actual Product Master
        name for a linked item, not just whatever the free-text
        description happens to say (Family 102 Test 2: 'the products
        displayed on the Order Detail screen are the same actual
        products selected during creation')."""
        return self.product.name if self.product else None

    @property
    def product_code(self):
        return self.product.product_code if self.product else None
