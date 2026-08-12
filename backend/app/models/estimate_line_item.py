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
    description = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # Material/Labor/Hardware/Installation/Transportation/Design/...
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(20), nullable=True)
    rate = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)  # quantity * rate, stored (not computed at read time)
    sort_order = Column(Integer, nullable=False, default=0)

    estimate = relationship("Estimate", back_populates="line_items")
