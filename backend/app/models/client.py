from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Client(BaseModel):
    __tablename__ = "clients"
    
    client_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    lead_source = Column(String(100), nullable=True)
    is_active = Column(Integer, default=1)
    remarks = Column(Text, nullable=True)

    payments = relationship("Payment", back_populates="client")
