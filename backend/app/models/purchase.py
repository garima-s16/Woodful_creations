from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Purchase(BaseModel):
    """Stock In / Purchase Register."""
    __tablename__ = "purchases"

    purchase_code = Column(String(20), unique=True, nullable=False, index=True)  # PUR-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # purchase_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expected_delivery_date = Column(DateTime, nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    rate = Column(Numeric(12, 2), nullable=False)
    taxable_value = Column(Numeric(12, 2), nullable=False)
    gst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    gst_amount = Column(Numeric(12, 2), nullable=False, default=0)
    invoice_total = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(String(20), nullable=False, default="Paid")
    # "Received" (default) - stock increases immediately, the only
    # behavior that existed before this field. "Ordered" - goods
    # requested from the supplier but not yet arrived; stock is
    # untouched until StockService.mark_purchase_received is called.
    # "Partially Received" - some but not all of `quantity` has
    # arrived; quantity_received tracks how much.
    receipt_status = Column(String(20), nullable=False, default="Received")
    quantity_received = Column(Numeric(12, 2), nullable=False, default=0)  # how much of `quantity` has actually arrived
    # Which location this purchase's stock is/was received into. Nullable -
    # unset means "use the material's primary location", preserving
    # behavior for callers that don't pass one. Kept on the Purchase itself
    # (not just the ledger entry) so an "Ordered" purchase remembers where
    # it's destined until StockService.mark_purchase_received actually
    # applies the receipt.
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    supplier = relationship("Supplier", back_populates="purchases")
    material = relationship("Material", back_populates="purchases")
    location = relationship("Location")
