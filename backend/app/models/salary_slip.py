from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class SalarySlip(BaseModel):
    """Monthly salary slip. Basic/DA/HRA + PF/TDS deduction fields are
    provided as plain editable numbers, NOT auto-calculated against actual
    Indian statutory slabs (PF %, TDS slabs, professional tax, etc. change
    by state/year and need a qualified payroll/accounting review) - treat
    the computed net_salary as basic + da + hra + overtime - deductions,
    with the actual PF/TDS figures entered by whoever runs payroll."""
    __tablename__ = "salary_slips"

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    business_id = Column(String(10), unique=True, index=True, nullable=True)
    month = Column(String(20), nullable=False)
    year = Column(String(4), nullable=False)
    working_days = Column(Numeric(5, 2), nullable=False, default=26)
    paid_days = Column(Numeric(5, 2), nullable=False, default=26)
    basic = Column(Numeric(12, 2), nullable=False, default=0)
    da = Column(Numeric(12, 2), nullable=False, default=0)  # Dearness Allowance
    hra = Column(Numeric(12, 2), nullable=False, default=0)  # House Rent Allowance
    overtime_amount = Column(Numeric(12, 2), nullable=False, default=0)
    pf_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    tds_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    other_deductions = Column(Numeric(12, 2), nullable=False, default=0)
    net_salary = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft")  # draft/finalized/paid

    employee = relationship("Employee")
