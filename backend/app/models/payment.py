from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from datetime import datetime
from app.core.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_type = Column(String)
    related_id = Column(Integer, index=True)
    amount = Column(Float, default=0.0)
    payment_date = Column(DateTime, index=True)
    payment_method = Column(String)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)