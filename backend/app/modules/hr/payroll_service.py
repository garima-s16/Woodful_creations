"""Family P0.43 - Payroll Intelligence. A summary aggregation over
already-authoritative data (SalarySlip.status, SalaryAdvance) - not a
second payroll engine. Answers "is payroll ready, what's pending, what
remains" for one month/year, plus the business-wide (not month-
specific) outstanding salary-advance picture, since an advance can
span more than one recovery month.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.hr.models import Employee, SalarySlip, SalaryAdvance


def get_payroll_summary(db: Session, month: str, year: str) -> dict:
    """One month's payroll state. employees_without_slip is a genuine
    "payroll not yet generated for them" finding (spec section 14 -
    "Payroll pending"), distinct from a slip that exists in "draft"
    status - the two are different findings and must not be
    conflated."""
    active_employees = db.query(Employee).filter(Employee.status == "Active").all()
    slips = db.query(SalarySlip).filter(SalarySlip.month == month, SalarySlip.year == year).all()
    slips_by_employee = {s.employee_id: s for s in slips}

    status_counts = {"draft": 0, "finalized": 0, "paid": 0}
    total_net_pending = Decimal("0")  # finalized but not yet paid
    total_net_paid = Decimal("0")
    total_advance_recovery = Decimal("0")
    for slip in slips:
        status_counts[slip.status] = status_counts.get(slip.status, 0) + 1
        total_advance_recovery += (slip.advance_deduction or Decimal("0"))
        if slip.status == "finalized":
            total_net_pending += (slip.net_salary or Decimal("0"))
        elif slip.status == "paid":
            total_net_paid += (slip.net_salary or Decimal("0"))

    employees_without_slip = [e for e in active_employees if e.id not in slips_by_employee]

    return {
        "month": month, "year": year,
        "total_active_employees": len(active_employees),
        "employees_with_slip": len(slips),
        "employees_without_slip": len(employees_without_slip),
        "employees_without_slip_names": [e.name for e in employees_without_slip],
        "status_counts": status_counts,
        "total_net_pending_payment": total_net_pending,
        "total_net_paid": total_net_paid,
        "total_advance_recovery_this_month": total_advance_recovery,
    }


def get_salary_advance_summary(db: Session) -> dict:
    """Business-wide (not month-specific), since one advance's
    recovery can genuinely span multiple payroll months (spec section
    10: "do not assume every advance must be recovered in one
    month")."""
    pending = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Pending").all()
    approved = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Approved").all()
    outstanding_total = sum((a.outstanding_amount for a in approved), Decimal("0"))
    fully_recovered = [a for a in approved if a.outstanding_amount <= 0]

    return {
        "pending_requests": len(pending),
        "approved_advances": len(approved),
        "fully_recovered_advances": len(fully_recovered),
        "advances_with_outstanding_balance": len(approved) - len(fully_recovered),
        "total_outstanding_amount": outstanding_total,
    }


def get_overtime_summary(db: Session, month: str, year: str) -> dict:
    """Real Attendance.overtime_hours records for the given month
    (parsed the same way salary_slips.py's own attendance-summary
    endpoint does) - which employees have approved overtime, and how
    much, never a second overtime calculation (Attendance.overtime_hours
    is the one authoritative, directly Master-set figure - see its own
    column comment)."""
    from datetime import datetime
    import calendar as _calendar
    from app.modules.hr.models import Attendance

    try:
        period_start = datetime.strptime(f"{month} {year}", "%B %Y")
    except ValueError:
        return {"month": month, "year": year, "error": "month must be a full month name, e.g. 'September', and year must be 4 digits", "employees": []}
    last_day = _calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)

    records = (
        db.query(Attendance)
        .filter(Attendance.date >= period_start, Attendance.date <= period_end, Attendance.overtime_hours > 0)
        .all()
    )
    by_employee: dict = {}
    for r in records:
        by_employee.setdefault(r.employee_id, Decimal("0"))
        by_employee[r.employee_id] += r.overtime_hours or Decimal("0")

    employee_ids = list(by_employee.keys())
    employees_by_id = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()} if employee_ids else {}

    return {
        "month": month, "year": year,
        "employees": [
            {"employee_id": eid, "employee_name": employees_by_id[eid].name if eid in employees_by_id else "Unknown", "total_overtime_hours": float(hours)}
            for eid, hours in by_employee.items()
        ],
    }
