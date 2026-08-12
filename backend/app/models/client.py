from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Client(BaseModel):
    """Client Master. total_orders/total_sales are derived (see
    ClientService) rather than stored, to avoid divergence from the
    orders table."""
    __tablename__ = "clients"

    client_code = Column(String(20), unique=True, nullable=False, index=True)  # CL-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # client_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="Active")  # Active / Inactive
    lead_source = Column(String(100), nullable=True)
    first_contact_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="client")
