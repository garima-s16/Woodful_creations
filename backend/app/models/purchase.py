from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel

class PurchaseOrder(BaseModel):
    __tablename__ = "purchase_orders"
    
    purchase_id = Column(String(20), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit = Column(String(50), nullable=False)
    rate = Column(Numeric(12, 2), nullable=False)
    taxable_value = Column(Numeric(12, 2), nullable=False)
    gst_percent = Column(Numeric(5, 2), default=18.00)
    gst_amount = Column(Numeric(12, 2), nullable=False)
    invoice_total = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(String(50), default="Unpaid")
    remarks = Column(Text, nullable=True)
    
    material = relationship("Material", back_populates="purchases")
    supplier = relationship("Supplier")
    
    def calculate_amounts(self):
        self.taxable_value = float(self.rate) * self.quantity
        self.gst_amount = float(self.taxable_value) * (float(self.gst_percent) / 100)
        self.invoice_total = float(self.taxable_value) + float(self.gst_amount)
        return self
