from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class EstimateLineItem(BaseModel):
    """A single priced item within an estimate - e.g. "Wardrobe",
    "Hardware", "Installation". Real per-item quantity/rate/amount, not a
    single flat material+labor figure - so an estimate can actually
    itemize what a client is being quoted for, not just a total."""
    __tablename__ = "estimate_line_items"

    estimate_id = Column(Integer, ForeignKey("estimates.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # Material/Labor/Hardware/Installation/Transportation/Design/...
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, stored (not computed at read time)
    sort_order = Column(Integer, nullable=False, default=0)
    # Optional link to the Product Master - what was actually quoted, when
    # it corresponds to a real catalog/custom product rather than a
    # freeform line (e.g. "Design consultation"). Nullable: an estimate
    # line item is never required to reference a product.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    # Custom/one-off line item (spec section 15): a genuine customer
    # request that doesn't exist in Product Master and shouldn't be
    # forced into it. When True, product_id stays null and this line
    # is exempt from the "Product ID is required" rule - description/
    # rate are still required as normal.
    is_custom_item = Column(Boolean, nullable=False, default=False)
    # Historical pricing snapshot (spec section 13): which priority
    # rule actually produced this line's rate, and the margin% used if
    # any - recorded once at creation and never recalculated, so a
    # later change to the Product's margin, a RateCard revision, or a
    # customer-specific override can never retroactively change what
    # this specific historical line says it charged.
    pricing_rule_applied = Column(String(40), nullable=True)  # one of app.utils.pricing_priority.PRICING_RULES
    applied_margin_percent = Column(Numeric(5, 2), nullable=True)

    estimate = relationship("Estimate", back_populates="line_items")
    product = relationship("Product", back_populates="estimate_line_items")

    @property
    def product_name(self):
        return self.product.name if self.product else None

    @property
    def product_code(self):
        return self.product.product_code if self.product else None
