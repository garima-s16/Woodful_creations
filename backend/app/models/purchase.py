from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Purchase(BaseModel):
    """Stock In / Purchase Register."""
    __tablename__ = "purchases"

    purchase_code = Column(String(20), unique=True, nullable=False, index=True)  # PUR-001
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
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

    supplier = relationship("Supplier", back_populates="purchases")
    material = relationship("Material", back_populates="purchases")
