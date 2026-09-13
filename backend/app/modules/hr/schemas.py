"""HR domain Pydantic schemas."""
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from datetime import date as date_type
from app.modules.hr.models import Employee, Attendance, Leave, SalarySlip, WorkingCalendarSettings, CompanyHoliday, SalaryAdvance, ATTENDANCE_STATUSES, SALARY_SLIP_STATUSES
from app.shared import validate_phone


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
    # Family 137 (Employee 360, section 13.9) - offboarding facts, set
    # explicitly by a master rather than inferred from a status change,
    # matching this project's human-in-the-loop rule for consequential
    # HR actions.
    exit_date: Optional[datetime] = None
    exit_reason: Optional[str] = None

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
    exit_date: Optional[datetime] = None
    exit_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmployeeLifecycleItemUpdate(BaseModel):
    """Family 137 (Employee 360, section 13.9) - toggling one
    onboarding/offboarding checklist item. is_complete is required
    (never inferred) - this is a human decision, not a derived fact,
    for every item this schema is used on (the auto-derived items
    reject direct toggling server-side - see hr/api.py)."""
    is_complete: bool
    remarks: Optional[str] = None


class AttendanceBase(BaseModel):
    date: datetime
    employee_id: int
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    standard_hours: Decimal = Decimal("8")
    attendance_status: str = "Present"
    # Family P0.43 - a real, directly-settable fact (see the model
    # column's own comment) - never derived from in_time/out_time.
    overtime_hours: Decimal = Decimal("0")
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

    @field_validator("overtime_hours")
    @classmethod
    def overtime_hours_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Overtime hours cannot be negative")
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


class AttendanceOvertimeAction(BaseModel):
    """Master's explicit 'Manage Overtime' action - one or more dates
    for one employee, and whether this call ADDS to whatever overtime
    already exists on each date or SETS it outright. These are
    deliberately different actions (spec sections 11/12): "Add" must
    never silently overwrite a value someone already recorded; "Set"
    is the explicit, intentional replacement."""
    employee_id: int
    dates: List[datetime]
    hours: Decimal
    mode: str = "add"  # "add" or "set"

    @field_validator("hours")
    @classmethod
    def hours_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Overtime hours cannot be negative")
        return v

    @field_validator("dates")
    @classmethod
    def dates_not_empty(cls, v: List[datetime]) -> List[datetime]:
        if not v:
            raise ValueError("At least one date must be provided")
        return v

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in ("add", "set"):
            raise ValueError("mode must be 'add' or 'set'")
        return v


class AttendanceUpdate(BaseModel):
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    attendance_status: Optional[str] = None
    overtime_hours: Optional[Decimal] = None
    remarks: Optional[str] = None

    @field_validator("overtime_hours")
    @classmethod
    def overtime_hours_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Overtime hours cannot be negative")
        return v

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

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # The model's own comment documents these three values, but
        # nothing previously enforced them - a typo or different
        # casing would silently never match anything that filters on
        # status (e.g. the payroll summary/business-risk payroll
        # signal, both of which query for the exact string "finalized").
        if v is None:
            return v
        if v not in SALARY_SLIP_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(sorted(SALARY_SLIP_STATUSES))}")
        return v

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
    # Family P0.44 - never on Create/Update (see _compute_net's own
    # comment); the only way this becomes non-zero is the salary
    # advance recovery action, so it is read-only here.
    advance_deduction: Decimal = Decimal("0")
    net_salary: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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


class SalaryAdvanceCreate(BaseModel):
    """Covers both the employee-initiated request AND the Master
    direct-advance workflow (spec section 8) - the difference is only
    who the authenticated caller is, enforced by the route, not a
    separate schema. employee_id is accepted here (needed for the
    Master-on-behalf case); an employee's own request always ignores
    whatever employee_id they send and uses their own, so an employee
    can never request on someone else's behalf by editing this field."""
    employee_id: int
    requested_amount: Decimal
    request_date: datetime
    reason: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("requested_amount")
    @classmethod
    def requested_amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Requested amount must be greater than zero")
        return v


class SalaryAdvanceApprove(BaseModel):
    """approved_amount is optional - omitting it means "approve exactly
    the requested amount" (spec section 7's "approve a different
    amount" is opt-in, not mandatory)."""
    approved_amount: Optional[Decimal] = None
    recovery_month: str
    recovery_year: str
    remarks: Optional[str] = None

    @field_validator("approved_amount")
    @classmethod
    def approved_amount_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Approved amount must be greater than zero")
        return v


class SalaryAdvanceReject(BaseModel):
    rejection_reason: Optional[str] = None


class SalaryAdvanceRecovery(BaseModel):
    """Links one recovery action to one real, existing SalarySlip -
    the spec's own "must use the authoritative payroll calculation"
    requirement means this cannot just be a number typed here; the
    route resolves the SalarySlip for (employee_id, month, year) and
    fails if it does not exist, rather than inventing one."""
    amount: Decimal
    month: str
    year: str

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Recovery amount must be greater than zero")
        return v


class SalaryAdvanceResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    employee_id: int
    employee_name: Optional[str] = None
    requested_amount: Decimal
    request_date: datetime
    reason: Optional[str] = None
    status: str
    approved_amount: Optional[Decimal] = None
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    recovery_month: Optional[str] = None
    recovery_year: Optional[str] = None
    recovered_amount: Decimal
    outstanding_amount: Decimal
    created_by: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        # Defect repair: every sibling *Response schema in this file
        # (EmployeeResponse, AttendanceResponse, LeaveResponse,
        # SalarySlipResponse, WorkingWeekdayResponse,
        # CompanyHolidayResponse, OvertimeRequestResponse) declares
        # this, because _serialize()/route handlers call
        # SalaryAdvanceResponse.model_validate(advance) directly on the
        # SQLAlchemy SalaryAdvance ORM instance, not a dict - without
        # from_attributes, pydantic v2 rejects a non-dict, non-model
        # input outright ("Input should be a valid dictionary or
        # instance of SalaryAdvanceResponse"), so every salary-advance
        # endpoint (list/create/get/approve/reject/recover) would raise
        # a ValidationError on its very first successful DB write. This
        # was the one *Response class in this file missing it.
        # employee_name isn't a real column (hr/api.py's _serialize()
        # fills it in afterward from advance.employee.name) and
        # outstanding_amount is a @property, not a Column, on the
        # SalaryAdvance model (see hr/models.py) - both still resolve
        # correctly via plain getattr, exactly like every sibling
        # schema above already relies on for their own computed/
        # relationship fields.
        from_attributes = True


class OvertimeRequestCreate(BaseModel):
    """Covers both the employee-initiated request AND a Master
    creating one on an employee's behalf - same pattern as
    SalaryAdvanceCreate. Always starts life as "Draft" (the route
    never accepts a status here)."""
    employee_id: int
    date: datetime
    requested_hours: Decimal
    reason: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("requested_hours")
    @classmethod
    def requested_hours_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Requested hours must be greater than zero")
        if v > 24:
            raise ValueError("Requested hours cannot exceed 24 for a single day")
        return v


class OvertimeRequestUpdate(BaseModel):
    """Only usable while status is still "Draft" - enforced by the
    route, not here."""
    date: Optional[datetime] = None
    requested_hours: Optional[Decimal] = None
    reason: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("requested_hours")
    @classmethod
    def requested_hours_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v <= 0 or v > 24):
            raise ValueError("Requested hours must be greater than zero and at most 24")
        return v


class OvertimeRequestApprove(BaseModel):
    """approved_hours is optional - omitting it means "approve exactly
    the requested hours" (same opt-in-different-amount pattern as
    SalaryAdvanceApprove)."""
    approved_hours: Optional[Decimal] = None
    remarks: Optional[str] = None

    @field_validator("approved_hours")
    @classmethod
    def approved_hours_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v <= 0 or v > 24):
            raise ValueError("Approved hours must be greater than zero and at most 24")
        return v


class OvertimeRequestReject(BaseModel):
    rejection_reason: Optional[str] = None


class OvertimeRequestResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    employee_id: int
    employee_name: Optional[str] = None
    date: datetime
    requested_hours: Decimal
    reason: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None
    approved_hours: Optional[Decimal] = None
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_by: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        # Explicit here (unlike SalaryAdvanceResponse, which this
        # schema otherwise mirrors) because _serialize() below builds
        # this via model_validate(overtime_request) on the live
        # SQLAlchemy row, which needs from_attributes to read object
        # attributes rather than requiring a dict.
        from_attributes = True
