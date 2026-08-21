from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Supplier(BaseModel):
    __tablename__ = "suppliers"

    supplier_code = Column(String(20), unique=True, nullable=False, index=True)  # SUP-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # supplier_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    payment_terms = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)

    materials = relationship("Material", back_populates="primary_supplier")
    purchases = relationship("Purchase", back_populates="supplier")
    supplier_materials = relationship("SupplierMaterial", back_populates="supplier", cascade="all, delete-orphan")
