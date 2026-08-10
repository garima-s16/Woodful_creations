from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Numeric
from datetime import datetime
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    material_type = Column(String, index=True)
    thickness = Column(Float, index=True)
    category = Column(String, index=True)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, default=0)
    min_quantity = Column(Integer, default=10)
    price_per_unit = Column(Numeric(12, 2), default=0)
    unit = Column(String, default="sheets")
    sku = Column(String, unique=True, nullable=True)
    supplier = Column(String, nullable=True)
    last_restocked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)