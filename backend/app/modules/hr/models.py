"""Workforce/HR domain models: Employee, Attendance, Leave, SalarySlip,
WorkingCalendarSettings, CompanyHoliday, SalaryAdvance.

Consolidated from employee.py + attendance.py + leave.py + salary_slip.py
+ working_calendar.py.
"""
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Date, Boolean, Text
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


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
    address = Column(Text, nullable=True)
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
    # Family P0.43 - a real, directly-settable fact, not derived from
    # in_time/out_time: the Master explicitly states whether there
    # were any overtime hours on a given day. Zero unless the Master
    # says otherwise - working_hours (below) is a separate, purely
    # informational clock-time figure and never feeds this.
    overtime_hours = Column(Numeric(5, 2), nullable=False, default=0)
    remarks = Column(Text, nullable=True)

    employee = relationship("Employee", back_populates="attendance_records")

    @property
    def working_hours(self):
        """Informational only (actual clock-in/out span, where
        recorded) - does not drive overtime_hours, which is the
        Master's own explicit figure (see its column comment)."""
        if not self.in_time or not self.out_time:
            return 0
        delta = self.out_time - self.in_time
        return round(delta.total_seconds() / 3600, 2)


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
    # Family P0.44 - the recovery amount applied against a SalaryAdvance
    # for this employee/month, kept as its own explicit column (not
    # folded into other_deductions) so recovery is independently
    # visible and traceable back to the SalaryAdvance it came from,
    # not blended into an undifferentiated "other" bucket. Defaults to
    # 0 - a slip created before this existed, or with no advance
    # recovery due, is unaffected.
    advance_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    net_salary = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft")  # draft/finalized/paid

    employee = relationship("Employee")


class WorkingCalendarSettings(BaseModel):
    """Single-row configuration: which weekdays are working days by
    default. A separate row per weekday (rather than one JSON blob)
    keeps this readable and directly editable via the existing
    Settings-page CRUD pattern, matching how every other lookup list
    in this app already works.

    weekday: 0=Monday ... 6=Sunday (Python's datetime.weekday() convention)."""
    __tablename__ = "working_calendar_weekdays"

    weekday = Column(String(10), unique=True, nullable=False)  # "Monday".."Sunday"
    is_working = Column(Boolean, nullable=False, default=True)


class CompanyHoliday(BaseModel):
    """A single calendar-date override. is_working=False means a
    company holiday (removes an otherwise-working day). is_working=True
    on a normally-off weekday means a declared special working day
    (adds a working day back). One table covers both cases from
    the same requirements, rather than two separate models."""
    __tablename__ = "company_holidays"

    date = Column(Date, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_working = Column(Boolean, nullable=False, default=False)  # False = holiday, True = special working day
    remarks = Column(Text, nullable=True)


class SalaryAdvance(BaseModel):
    """Family P0.44 - Salary Advance Management. A full workflow, not a
    single number: Employee requests -> Master approves/rejects (at a
    possibly different amount than requested) -> recovery happens
    against real SalarySlips over one or more payroll months, tracked
    here so "how much is still outstanding" is always a real,
    queryable fact rather than something recomputed by re-reading
    every SalarySlip each time.

    requested_amount is never overwritten once set (the spec's own
    "Requested Amount remains historical" rule) - approved_amount is
    the separate, authoritative figure recovery is actually calculated
    against once status becomes "Approved".
    """
    __tablename__ = "salary_advances"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    requested_amount = Column(Numeric(12, 2), nullable=False)
    request_date = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=True)
    # Pending / Approved / Rejected - a request never skips Pending;
    # even a Master-initiated advance starts Pending and is then
    # explicitly approved (spec section 8's own numbered steps), so
    # the same approval audit trail applies whether the employee or
    # the Master initiated it.
    status = Column(String(20), nullable=False, default="Pending")
    approved_amount = Column(Numeric(12, 2), nullable=True)
    approved_by = Column(String(255), nullable=True)
    approval_date = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    # The recovery month/year this advance is scheduled against - set
    # at approval time, but recovery can genuinely span more than one
    # payroll month (spec: "do not assume every advance must be
    # recovered in one month"), so this is where recovery STARTS, not
    # a claim that it finishes there.
    recovery_month = Column(String(20), nullable=True)
    recovery_year = Column(String(4), nullable=True)
    recovered_amount = Column(Numeric(12, 2), nullable=False, default=0)
    # Who actually created this row - the employee themselves, or a
    # Master acting on their behalf (spec section 8) - distinct from
    # approved_by, which is always whoever approved it.
    created_by = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)

    employee = relationship("Employee")

    @property
    def outstanding_amount(self):
        """Zero for anything not Approved - a Pending or Rejected
        request has no recoverable balance at all, not because
        nothing has been recovered yet but because there is nothing
        approved to recover against."""
        from decimal import Decimal
        if self.status != "Approved":
            return Decimal("0")
        return (self.approved_amount or Decimal("0")) - (self.recovered_amount or Decimal("0"))
