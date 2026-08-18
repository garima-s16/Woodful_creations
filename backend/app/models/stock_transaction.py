from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class StockTransfer(BaseModel):
    """A real, audited record of moving a material from one location to
    another. Material.location_id is a single field (no per-location
    quantity breakdown - see docs/UI_UX_BACKLOG.md item 1 on why that's
    deliberately deferred until the full stock ledger exists), so a
    transfer here means: log the move, then update that single field -
    not maintain a second, parallel stock-by-location number."""
    __tablename__ = "stock_transfers"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    transferred_by = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)

    material = relationship("Material")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])


class StockAdjustment(BaseModel):
    """An audited correction to current_stock - never a silent direct
    edit. Every adjustment records a reason and a signed quantity delta
    (positive = increase, negative = decrease), same accountability
    pattern already used for Purchase (+stock) and Issue (-stock)."""
    __tablename__ = "stock_adjustments"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    adjustment_type = Column(String(30), nullable=False)  # Physical Count / Damage / Wastage / Theft-Loss / Correction
    quantity_delta = Column(Numeric(12, 2), nullable=False)  # signed: +5 or -5
    stock_before = Column(Numeric(12, 2), nullable=False)
    stock_after = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=False)
    adjusted_by = Column(String(100), nullable=True)

    material = relationship("Material")
