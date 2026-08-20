from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class StockLedgerEntry(BaseModel):
    """One immutable row per stock-affecting event - Receipt (purchase
    or return), Issue, Adjustment, or Transfer. Never updated or deleted
    once written. balance_after records the running material-wide
    current_stock immediately after this entry, so the ledger can be
    replayed and checked against Material.current_stock at any time
    (StockService.verify_stock_matches_ledger does exactly this).
    reference_type/reference_id link back to the actual Purchase/
    Issue/StockAdjustment/StockTransfer row that caused the change, so
    every number here traces to a real business record - never a
    synthetic entry.

    location_id identifies WHERE the movement happened - nullable for
    backward compatibility with entries written before multi-location
    support existed. A Transfer is recorded as two entries (a negative
    delta at from_location, a positive delta at to_location) whose
    quantity_delta sums to zero, so the material-wide total (and
    verify_stock_matches_ledger) is completely unaffected by transfers -
    only the per-location breakdown changes. Per-location balance is
    always DERIVED by summing quantity_delta grouped by location_id -
    never stored as an independent number (see
    StockService.get_location_balances).
    """
    __tablename__ = "stock_ledger_entries"

    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    entry_type = Column(String(20), nullable=False)  # Receipt / Issue / Adjustment / Transfer
    quantity_delta = Column(Numeric(12, 2), nullable=False)  # signed: +5 or -5
    balance_after = Column(Numeric(12, 2), nullable=False)
    reference_type = Column(String(20), nullable=True)  # purchase / issue / stock_adjustment / stock_transfer
    reference_id = Column(Integer, nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    remarks = Column(Text, nullable=True)

    material = relationship("Material")
    location = relationship("Location")
