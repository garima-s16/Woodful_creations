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
    designation = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True, index=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    manager = Column(String(255), nullable=True)  # supervisor's name - kept as free text (not an FK to
    # another Employee row) since not every org chart is a clean single-manager tree, and this avoids a
    # self-referential FK cascade-delete/reassignment problem for a field that's "where applicable" anyway
    joining_date = Column(DateTime, nullable=True)
    monthly_salary = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="Active")
    emergency_contact = Column(String(20), nullable=True)
    remarks = Column(Text, nullable=True)
    # Payroll/statutory identifiers - needed for salary slip generation.
    # All nullable: not administrative data every employee record will
    # have from day one.
    pan = Column(String(10), nullable=True)
    uan = Column(String(20), nullable=True)
    bank_name = Column(String(100), nullable=True)
    bank_account_number = Column(String(30), nullable=True)
    tax_regime = Column(String(10), nullable=True)  # Old / New

    attendance_records = relationship("Attendance", back_populates="employee")
    daily_tasks = relationship("DailyTask", back_populates="employee")

    @property
    def daily_wage(self):
        """Monthly salary / 26 working days, matching the source workbook's formula."""
        return round(float(self.monthly_salary or 0) / 26, 2)
