from sqlalchemy import Column, String, Numeric, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Employee(BaseModel):
    """Employee Master."""
    __tablename__ = "employees"

    employee_code = Column(String(20), unique=True, nullable=False, index=True)  # EMP-001
    # Opaque 10-char external identifier (e.g. A7K92P4XQ1) - separate from
    # employee_code, which stays as the human-scannable sequential reference.
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=True, index=True)
    phone = Column(String(20), nullable=True)
    joining_date = Column(DateTime, nullable=True)
    monthly_salary = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="Active")
    emergency_contact = Column(String(20), nullable=True)
    remarks = Column(Text, nullable=True)

    attendance_records = relationship("Attendance", back_populates="employee")
    daily_tasks = relationship("DailyTask", back_populates="employee")

    @property
    def daily_wage(self):
        """Monthly salary / 26 working days, matching the source workbook's formula."""
        return round(float(self.monthly_salary or 0) / 26, 2)
