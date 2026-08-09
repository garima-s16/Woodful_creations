from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel

class MaterialIssue(BaseModel):
    __tablename__ = "material_issues"
    
    issue_id = Column(String(20), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity_issued = Column(Integer, nullable=False)
    unit = Column(String(50), nullable=False)
    issued_to = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    purpose = Column(Text, nullable=True)
    approved_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)
    
    material = relationship("Material", back_populates="issues")
    order = relationship("Order", back_populates="material_issues")
