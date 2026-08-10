from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Numeric
from datetime import datetime
from app.core.database import Base

class ClientProject(Base):
    __tablename__ = "client_projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, index=True)
    project_name = Column(String, index=True)
    description = Column(Text, nullable=True)
    design_status = Column(String, default="pending")
    execution_status = Column(String, default="pending")
    delivery_status = Column(String, default="pending")
    estimated_delivery = Column(DateTime, nullable=True)
    cost = Column(Numeric(12, 2), default=0)
    amount_paid = Column(Numeric(12, 2), default=0)
    amount_pending = Column(Numeric(12, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)