from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Payment(BaseModel):
    """Client Payment Register."""
    __tablename__ = "payments"

    receipt_code = Column(String(20), unique=True, nullable=False, index=True)  # RCPT-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # receipt_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    payment_type = Column(String(50), nullable=False)  # Advance / Progress Payment / Internal
    payment_mode = Column(String(50), nullable=False)  # Cash / UPI / Bank Transfer / Cheque / Card / Other
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    reference_number = Column(String(100), nullable=True)
    received_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    order = relationship("Order", back_populates="payments")
    documents = relationship("PaymentDocument", back_populates="payment", cascade="all, delete-orphan")
