from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Material(BaseModel):
    """Live Material Stock Master. current_stock/total_purchased/total_issued
    are maintained transactionally by StockService whenever a Purchase or
    Issue is recorded - see services/stock_service.py."""
    __tablename__ = "materials"

    material_code = Column(String(20), unique=True, nullable=False, index=True)  # MAT-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # material_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True, index=True)
    brand_grade = Column(String(100), nullable=True)
    thickness_size = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False)

    opening_stock = Column(Integer, nullable=False, default=0)
    total_purchased = Column(Integer, nullable=False, default=0)
    total_issued = Column(Integer, nullable=False, default=0)
    current_stock = Column(Integer, nullable=False, default=0, index=True)
    minimum_stock = Column(Integer, nullable=False, default=0)

    average_rate = Column(Numeric(12, 2), nullable=False, default=0)

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    location = Column(String(100), nullable=True)

    primary_supplier = relationship("Supplier", back_populates="materials")
    purchases = relationship("Purchase", back_populates="material")
    issues = relationship("Issue", back_populates="material")

    @property
    def stock_value(self):
        return round(float(self.current_stock or 0) * float(self.average_rate or 0), 2)

    @property
    def stock_status(self):
        if (self.current_stock or 0) <= 0:
            return "OUT OF STOCK"
        if (self.current_stock or 0) <= (self.minimum_stock or 0):
            return "LOW STOCK"
        return "STOCK OK"
