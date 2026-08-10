from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Supplier(BaseModel):
    __tablename__ = "suppliers"

    supplier_code = Column(String(20), unique=True, nullable=False, index=True)  # SUP-001
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    payment_terms = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)

    materials = relationship("Material", back_populates="primary_supplier")
    purchases = relationship("Purchase", back_populates="supplier")
