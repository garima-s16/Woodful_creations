from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Client(BaseModel):
    """Client Master. total_orders/total_sales are derived (see
    ClientService) rather than stored, to avoid divergence from the
    orders table."""
    __tablename__ = "clients"

    client_code = Column(String(20), unique=True, nullable=False, index=True)  # CL-001
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    lead_source = Column(String(100), nullable=True)
    first_contact_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="client")
