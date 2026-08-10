from sqlalchemy import Column, Integer, String, DateTime, Float, Numeric
from datetime import datetime
from app.core.database import Base

class SalarySlip(Base):
    __tablename__ = "salary_slips"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, index=True)
    month = Column(String)
    year = Column(String)
    basic_salary = Column(Numeric(12, 2), default=0)
    allowances = Column(Numeric(12, 2), default=0)
    deductions = Column(Numeric(12, 2), default=0)
    net_salary = Column(Numeric(12, 2), default=0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)