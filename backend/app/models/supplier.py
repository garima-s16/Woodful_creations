from sqlalchemy import Column, String, Integer, Numeric, Text
from app.models.base import BaseModel

class Supplier(BaseModel):
    __tablename__ = "suppliers"
    
    supplier_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    gstin = Column(String(50), nullable=True, index=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    payment_terms = Column(String(100), nullable=True)
    is_active = Column(Integer, default=1)
    remarks = Column(Text, nullable=True)
