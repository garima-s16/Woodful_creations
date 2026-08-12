from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Attendance(BaseModel):
    """Employee Attendance & Overtime."""
    __tablename__ = "attendance"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    date = Column(DateTime, nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    in_time = Column(DateTime, nullable=True)
    out_time = Column(DateTime, nullable=True)
    standard_hours = Column(Numeric(5, 2), nullable=False, default=8)
    attendance_status = Column(String(20), nullable=False, default="Present")
    remarks = Column(Text, nullable=True)

    employee = relationship("Employee", back_populates="attendance_records")

    @property
    def working_hours(self):
        if not self.in_time or not self.out_time:
            return 0
        delta = self.out_time - self.in_time
        return round(delta.total_seconds() / 3600, 2)

    @property
    def overtime_hours(self):
        worked = self.working_hours
        std = float(self.standard_hours or 0)
        return round(max(worked - std, 0), 2)
