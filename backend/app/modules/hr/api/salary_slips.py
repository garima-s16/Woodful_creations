from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.audit.audit import log_action
from app.modules.hr.models import SalarySlip, Attendance, Employee
from app.modules.hr.working_calendar_service import compute_working_days, compute_salary_days
from app.modules.hr.schemas import SalarySlipCreate, SalarySlipUpdate, SalarySlipResponse
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/salary-slips", tags=["salary-slips"])


def _compute_net(data) -> None:
    gross = data.basic + data.da + data.hra + data.overtime_amount
    # advance_deduction is never on SalarySlipCreate/Update - the only
    # way it becomes non-zero is the salary-advance recovery action
    # (Family P0.44), which sets it directly on the model and calls
    # this same function to recompute net_salary rather than
    # duplicating the arithmetic. getattr keeps this function safe to
    # call with either a Create/Update schema (no such field, so 0)
    # or the SQLAlchemy model itself (a real, possibly non-zero value).
    advance_deduction = getattr(data, "advance_deduction", None) or Decimal("0")
    deductions = data.pf_deduction + data.tds_deduction + data.other_deductions + advance_deduction
    return gross - deductions


@router.get("/attendance-summary")
def suggest_from_attendance(employee_id: int, month: str, year: str, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    """Suggested working_days/paid_days/overtime_amount derived from this
    employee's real Attendance records for the given month - the master
    reviews and can adjust every value before actually saving a salary
    slip. Never writes anything itself. Day-value rule is explicit, not
    hidden: Present = 1 day, Half Day = 0.5 day,
    Absent/Leave = 0 (unpaid unless the master adjusts). working_days
    and the overtime hourly rate both come from the actual configured
    working calendar for THIS specific month (weekends/holidays/special
    working days), never a fixed assumption - a different month can and
    will produce a different total."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        period_start = datetime.strptime(f"{month} {year}", "%B %Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August', and year must be 4 digits")
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)

    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= period_start, Attendance.date <= period_end,
    ).all()

    working_days_this_month = compute_working_days(db, period_start.year, period_start.month)
    # Family P0.43's own explicit formula (Monday-Saturday working
    # days minus APPROVED leave) - a theoretical full-pay day count,
    # distinct from suggested_paid_days below (which reflects actual
    # recorded attendance and can differ, e.g. an unmarked absence
    # with no formal Leave record behind it). Both are given so the
    # Master can see and reconcile the difference, not one silently
    # replacing the other.
    salary_days_breakdown = compute_salary_days(db, employee_id, period_start.year, period_start.month)

    day_value = {"Present": 1, "Half Day": 0.5, "Absent": 0, "Leave": 0}
    paid_days = sum(day_value.get(r.attendance_status, 0) for r in records)
    total_overtime_hours = sum(r.overtime_hours for r in records)
    standard_hours_per_day = float(records[0].standard_hours) if records else 8
    daily_rate_this_month = (float(employee.monthly_salary or 0) / working_days_this_month) if working_days_this_month else 0
    hourly_rate = daily_rate_this_month / standard_hours_per_day if standard_hours_per_day else 0
    overtime_amount = round(total_overtime_hours * hourly_rate, 2)

    return {
        "employee_id": employee_id,
        "records_found": len(records),
        "suggested_working_days": working_days_this_month,
        "suggested_paid_days": paid_days,
        "total_overtime_hours": round(total_overtime_hours, 2),
        "suggested_overtime_amount": overtime_amount,
        "calendar_days": salary_days_breakdown["calendar_days"],
        "leave_days": salary_days_breakdown["leave_days"],
        "salary_days": salary_days_breakdown["salary_days"],
        "note": "Derived from Attendance records and the configured working calendar for this period - review before saving.",
    }


@router.get("/payroll-summary")
def payroll_summary(month: str, year: str, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family P0.43 - pure aggregation over SalarySlip.status and
    SalaryAdvance (see hr/payroll_service.py) - not a second payroll
    engine. Master-only: this is company-wide financial/payroll
    information."""
    from app.modules.hr.payroll_service import get_payroll_summary, get_salary_advance_summary
    return {
        **get_payroll_summary(db, month, year),
        "salary_advances": get_salary_advance_summary(db),
    }


@router.get("/", response_model=List[SalarySlipResponse])
def list_salary_slips(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    return query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()


@router.post("/", response_model=SalarySlipResponse, status_code=201)
def create_salary_slip(data: SalarySlipCreate, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        period_start = datetime.strptime(f"{data.month} {data.year}", "%B %Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August', and year must be 4 digits")

    if employee.joining_date:
        joining_period = employee.joining_date.replace(day=1)
        if period_start < joining_period:
            raise HTTPException(
                status_code=400,
                detail="Salary slip cannot be generated before the employee's joining date.",
            )

    existing = db.query(SalarySlip).filter(
        SalarySlip.employee_id == data.employee_id, SalarySlip.month == data.month, SalarySlip.year == data.year,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Salary slip for this employee/month/year already exists")

    for _ in range(5):
        net_salary = _compute_net(data)
        slip = SalarySlip(**data.dict(), net_salary=net_salary, business_id=generate_business_id(db))
        db.add(slip)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(slip)
        log_action(db, request, user_id=auth.get("user_id"), action="create_salary_slip", module_name="salary_slips",
                   record_id=slip.id, new_value={
                       "employee_id": slip.employee_id, "month": slip.month, "year": slip.year,
                       "net_salary": float(net_salary),
                   })
        return slip
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{slip_id}", response_model=SalarySlipResponse)
def get_salary_slip(slip_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    if auth.get("role", "user") not in ("master",) and slip.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
    return slip


@router.put("/{slip_id}", response_model=SalarySlipResponse)
def update_salary_slip(slip_id: int, data: SalarySlipUpdate, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    updates = data.dict(exclude_unset=True)
    new_working_days = updates.get("working_days", slip.working_days)
    new_paid_days = updates.get("paid_days", slip.paid_days)
    if new_paid_days > new_working_days:
        raise HTTPException(status_code=400, detail="paid_days cannot exceed working_days")

    def _serializable(field):
        value = getattr(slip, field)
        return float(value) if isinstance(value, (int, float, Decimal)) else value

    old_value = {field: _serializable(field) for field in updates}
    for field, value in updates.items():
        setattr(slip, field, value)
    slip.net_salary = _compute_net(slip)
    db.add(slip)
    db.commit()
    db.refresh(slip)
    new_value = {field: _serializable(field) for field in updates}
    log_action(db, request, user_id=auth.get("user_id"), action="update_salary_slip", module_name="salary_slips",
               record_id=slip.id, old_value=old_value, new_value=new_value)
    return slip
