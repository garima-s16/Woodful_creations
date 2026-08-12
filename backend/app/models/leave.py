from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Leave(BaseModel):
    """Employee leave request/record - PL (Privileged Leave), CL (Casual
    Leave), SL (Sick Leave), matching standard Indian HR leave categories."""
    __tablename__ = "leaves"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(String(20), nullable=False)  # PL / CL / SL
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)
    days = Column(Numeric(4, 1), nullable=False, default=1)
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="Pending", index=True)  # Pending/Approved/Rejected
    approved_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    employee = relationship("Employee")
