"""HR domain schemas - employees, attendance, leave, payroll, and the
working calendar (weekdays + company holidays). Consolidated from five
separate modules that all belong to the same "human resources" feature
area."""
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime, date as date_type

from app.shared.validators import validate_phone

# --- Employee -----------------------------------------------------------


class EmployeeBase(BaseModel):
    employee_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    designation: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    manager: Optional[str] = None
    joining_date: Optional[datetime] = None
    monthly_salary: Decimal = Decimal("0")
    status: str = "Active"
    emergency_contact: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # Phone stays optional for an employee (unlike Client Master,
        # where it's mandatory) - but IF one is given, it must be
        # exactly 10 digits, same rule and same exact message as
        # Client Master. emergency_contact is left freeform (it may
        # legitimately include a name/relation, not just a bare number).
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    manager: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    status: Optional[str] = None
    emergency_contact: Optional[str] = None
    remarks: Optional[str] = None
    pan: Optional[str] = None
    uan: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    tax_regime: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v


class EmployeeResponse(EmployeeBase):
    id: int
    business_id: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    daily_wage: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Attendance -----------------------------------------------------------

# The closed set of statuses payroll's day-value calculation
# (salary_slips.py's suggest_from_attendance) actually recognizes -
# any other string silently falls back to 0 paid days there, so it
# must be rejected here rather than accepted and mispriced later.
ATTENDANCE_STATUSES = {"Present", "Half Day", "Absent", "Leave"}


class AttendanceBase(BaseModel):
    date: datetime
    employee_id: int
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    standard_hours: Decimal = Decimal("8")
    attendance_status: str = "Present"
    remarks: Optional[str] = None

    @field_validator("date")
    @classmethod
    def date_is_calendar_day_only(cls, v: datetime) -> datetime:
        """`date` identifies which calendar day this record belongs to,
        not a clock time (in_time/out_time carry the actual times) - it
        is normalized to midnight so the database's per-employee/per-day
        unique index (see attendance route + migration 0060) genuinely
        enforces one record per calendar day, even if a caller supplies
        a non-midnight timestamp."""
        return datetime(v.year, v.month, v.day)

    @field_validator("standard_hours")
    @classmethod
    def standard_hours_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Standard hours cannot be negative")
        return v

    @field_validator("attendance_status")
    @classmethod
    def attendance_status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in ATTENDANCE_STATUSES:
            raise ValueError(f"Attendance status must be one of: {', '.join(sorted(ATTENDANCE_STATUSES))}")
        return v

    @model_validator(mode="after")
    def out_time_not_before_in_time(self):
        if self.in_time is not None and self.out_time is not None and self.out_time < self.in_time:
            raise ValueError("Out time cannot be before in time")
        return self


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    attendance_status: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("attendance_status")
    @classmethod
    def attendance_status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in ATTENDANCE_STATUSES:
            raise ValueError(f"Attendance status must be one of: {', '.join(sorted(ATTENDANCE_STATUSES))}")
        return v

    @model_validator(mode="after")
    def out_time_not_before_in_time(self):
        if self.in_time is not None and self.out_time is not None and self.out_time < self.in_time:
            raise ValueError("Out time cannot be before in time")
        return self


class AttendanceResponse(AttendanceBase):
    id: int
    business_id: str
    working_hours: float
    overtime_hours: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Leave -----------------------------------------------------------


class LeaveBase(BaseModel):
    employee_id: int
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None


class LeaveCreate(LeaveBase):
    """`days` is deliberately NOT accepted from the client - it is always
    computed server-side (inclusive calendar-day count) in the leaves route,
    so a bad frontend calculation (or a tampered request) can never produce
    a 0/negative/NaN value in the database."""
    pass


class LeaveUpdate(BaseModel):
    status: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class LeaveResponse(LeaveBase):
    id: int
    business_id: str
    days: Decimal
    status: str
    approved_by: Optional[str]
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Salary Slip -----------------------------------------------------------


class SalarySlipBase(BaseModel):
    employee_id: int
    month: str
    year: str
    working_days: Decimal = Decimal("26")
    paid_days: Decimal = Decimal("26")
    basic: Decimal = Decimal("0")
    da: Decimal = Decimal("0")
    hra: Decimal = Decimal("0")
    overtime_amount: Decimal = Decimal("0")
    pf_deduction: Decimal = Decimal("0")
    tds_deduction: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")

    @field_validator("working_days", "paid_days")
    @classmethod
    def _must_be_positive(cls, v, info):
        if v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0")
        return v

    @model_validator(mode="after")
    def _paid_days_within_working_days(self):
        if self.paid_days > self.working_days:
            raise ValueError("paid_days cannot exceed working_days")
        return self


class SalarySlipCreate(SalarySlipBase):
    @field_validator("basic", "da", "hra", "overtime_amount", "pf_deduction", "tds_deduction", "other_deductions")
    @classmethod
    def _monetary_component_not_negative(cls, v, info):
        if v < 0:
            raise ValueError(f"{info.field_name} cannot be negative")
        return v


class SalarySlipUpdate(BaseModel):
    status: Optional[str] = None
    working_days: Optional[Decimal] = None
    paid_days: Optional[Decimal] = None
    pf_deduction: Optional[Decimal] = None
    tds_deduction: Optional[Decimal] = None
    other_deductions: Optional[Decimal] = None

    @field_validator("working_days", "paid_days")
    @classmethod
    def _must_be_positive(cls, v, info):
        if v is not None and v <= 0:
            raise ValueError(f"{info.field_name} must be greater than 0")
        return v

    @field_validator("pf_deduction", "tds_deduction", "other_deductions")
    @classmethod
    def _deduction_not_negative(cls, v, info):
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} cannot be negative")
        return v


class SalarySlipResponse(SalarySlipBase):
    id: int
    business_id: str
    net_salary: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Working Calendar (weekdays + company holidays) -----------------------


class WorkingWeekdayUpdate(BaseModel):
    is_working: bool


class WorkingWeekdayResponse(BaseModel):
    id: int
    weekday: str
    is_working: bool

    class Config:
        from_attributes = True


class CompanyHolidayBase(BaseModel):
    date: date_type
    name: str
    is_working: bool = False  # False = holiday, True = declared special working day
    remarks: Optional[str] = None


class CompanyHolidayCreate(CompanyHolidayBase):
    pass


class CompanyHolidayUpdate(BaseModel):
    date: Optional[date_type] = None
    name: Optional[str] = None
    is_working: Optional[bool] = None
    remarks: Optional[str] = None


class CompanyHolidayResponse(CompanyHolidayBase):
    id: int

    class Config:
        from_attributes = True
