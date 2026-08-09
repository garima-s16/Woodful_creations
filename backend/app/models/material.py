from sqlalchemy import Column, String, Integer, Numeric, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Material(BaseModel):
    __tablename__ = "materials"
    
    material_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    brand_grade = Column(String(255), nullable=True)
    thickness_size = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=False)
    opening_stock = Column(Integer, default=0)
    total_purchased = Column(Integer, default=0)
    total_issued = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)
    minimum_stock = Column(Integer, default=10)
    is_active = Column(Integer, default=1)
    
    purchases = relationship("PurchaseOrder", back_populates="material")
    issues = relationship("MaterialIssue", back_populates="material")
    
    def calculate_current_stock(self):
        self.current_stock = self.opening_stock + self.total_purchased - self.total_issued
        return self.current_stock
    
    def get_stock_status(self):
        if self.current_stock <= 0:
            return "OUT_OF_STOCK"
        elif self.current_stock <= self.minimum_stock:
            return "LOW_STOCK"
        else:
            return "STOCK_OK"
