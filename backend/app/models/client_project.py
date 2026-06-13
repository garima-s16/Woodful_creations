from sqlalchemy import Column, Integer, String, DateTime, Float, Text
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
    cost = Column(Float, default=0.0)
    amount_paid = Column(Float, default=0.0)
    amount_pending = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)