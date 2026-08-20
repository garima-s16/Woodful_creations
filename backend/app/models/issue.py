from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Issue(BaseModel):
    """Stock Out / Material Issue Register."""
    __tablename__ = "issues"

    issue_code = Column(String(20), unique=True, nullable=False, index=True)  # ISS-001
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    quantity_issued = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    issued_to = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    purpose = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)
    # Which location this material was issued from. Nullable - unset means
    # "the material's primary location", preserving behavior for existing
    # callers that don't pass one.
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    order = relationship("Order", back_populates="issues")
    material = relationship("Material", back_populates="issues")
    location = relationship("Location")
