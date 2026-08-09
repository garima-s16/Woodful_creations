from sqlalchemy import Column, String, Integer
from app.models.base import BaseModel

class ProjectStatus(BaseModel):
    __tablename__ = "project_statuses"
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    display_order = Column(Integer, default=0)

class Priority(BaseModel):
    __tablename__ = "priorities"
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)

class PaymentMode(BaseModel):
    __tablename__ = "payment_modes"
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)

class LeadSource(BaseModel):
    __tablename__ = "lead_sources"
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)

class ProjectType(BaseModel):
    __tablename__ = "project_types"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)

class ExpenseCategory(BaseModel):
    __tablename__ = "expense_categories"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
