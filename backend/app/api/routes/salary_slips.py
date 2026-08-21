from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action
from app.models.salary_slip import SalarySlip
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.services.working_calendar_service import compute_working_days
from app.schemas.salary_slip import SalarySlipCreate, SalarySlipUpdate, SalarySlipResponse
from app.utils.id_generator import generate_business_id

router = APIRouter(prefix="/api/salary-slips", tags=["salary-slips"])


def _compute_net(data) -> None:
    gross = data.basic + data.da + data.hra + data.overtime_amount
    deductions = data.pf_deduction + data.tds_deduction + data.other_deductions
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
        "note": "Derived from Attendance records and the configured working calendar for this period - review before saving.",
    }


@router.get("/", response_model=List[SalarySlipResponse])
def list_salary_slips(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
        employee_id = own_employee_id
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    return query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()


@router.post("/", response_model=SalarySlipResponse, status_code=201)
def create_salary_slip(data: SalarySlipCreate, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
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
    slip.net_salary = slip.basic + slip.da + slip.hra + slip.overtime_amount - slip.pf_deduction - slip.tds_deduction - slip.other_deductions
    db.add(slip)
    db.commit()
    db.refresh(slip)
    new_value = {field: _serializable(field) for field in updates}
    log_action(db, request, user_id=auth.get("user_id"), action="update_salary_slip", module_name="salary_slips",
               record_id=slip.id, old_value=old_value, new_value=new_value)
    return slip
