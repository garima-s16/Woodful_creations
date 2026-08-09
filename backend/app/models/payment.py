from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel

class Payment(BaseModel):
    __tablename__ = "payments"
    
    receipt_id = Column(String(20), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    payment_type = Column(String(50), nullable=False)
    payment_mode = Column(String(50), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    reference_number = Column(String(100), nullable=True, index=True)
    received_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)
    
    order = relationship("Order", back_populates="payments")
    client = relationship("Client", back_populates="payments")
