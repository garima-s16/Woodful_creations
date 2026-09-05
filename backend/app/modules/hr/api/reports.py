"""HR-domain report exports: employees, attendance, leaves, payroll,
salary slip PDF, and company holidays. Split out of the former
monolithic reports.py - see modules/inventory/api/reports.py's docstring for
why."""
import calendar
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.hr.models import SalarySlip, Employee, CompanyHoliday, Attendance, Leave
from app.shared.exporters import build_workbook, xlsx_response
from app.modules.hr.pdf_generator import generate_salary_slip_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@router.get("/employees.xlsx")
def export_employees(
    search: Optional[str] = Query(None), department: Optional[str] = Query(None),
    status: Optional[str] = Query(None), db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Employee Directory export (P5) - mirrors GET /api/employees/'s
    search/department/status filters."""
    query = db.query(Employee)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like))
            | (Employee.designation.ilike(like)) | (Employee.phone.ilike(like)) | (Employee.email.ilike(like))
        )
        filters_applied.append(f'Search: "{search}"')
    if department:
        query = query.filter(Employee.department == department)
        filters_applied.append(f"Department: {department}")
    if status:
        query = query.filter(Employee.status == status)
        filters_applied.append(f"Status: {status}")

    employees = query.order_by(Employee.name).all()
    rows = [{
        "employee_id": e.business_id or "", "name": e.name, "designation": e.designation or "",
        "department": e.department or "", "phone": e.phone or "", "email": e.email or "",
        "joining_date": e.joining_date.strftime("%d-%m-%Y") if e.joining_date else "",
        "status": e.status, "manager": e.manager or "",
    } for e in employees]
    columns = ["employee_id", "name", "designation", "department", "phone", "email",
               "joining_date", "status", "manager"]
    headers = ["Employee ID", "Employee Name", "Designation", "Department", "Phone", "Email",
               "Joining Date", "Employment Status", "Manager/Supervisor"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Employees", str(len(employees)))]
    active_count = sum(1 for e in employees if e.status == "Active")
    summary.append(("Active", str(active_count)))
    summary.append(("Inactive/Other", str(len(employees) - active_count)))

    buffer = build_workbook([{
        "sheet_name": "Employees", "title": "EMPLOYEE DIRECTORY",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": summary,
    }])
    filename = f"employee_directory_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/attendance.xlsx")
def export_attendance(
    employee_id: Optional[int] = Query(None), month: Optional[str] = Query(None), year: Optional[str] = Query(None),
    attendance_status: Optional[str] = Query(None), overtime_only: bool = Query(False),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Attendance export - overtime_only covers "Overtime Excel" as a
    filtered view of the same data rather than a separate endpoint,
    since it's the same model with the same columns, just narrowed to
    records where overtime_hours > 0."""
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own attendance records.")
        if not own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own attendance records.")
        employee_id = own_employee_id

    query = db.query(Attendance).options(selectinload(Attendance.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if month and year:
        try:
            period_start = datetime.strptime(f"{month} {year}", "%B %Y")
            last_day = calendar.monthrange(period_start.year, period_start.month)[1]
            period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)
            query = query.filter(Attendance.date >= period_start, Attendance.date <= period_end)
            filters_applied.append(f"Period: {month} {year}")
        except ValueError:
            raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August'")
    if attendance_status:
        query = query.filter(Attendance.attendance_status == attendance_status)
        filters_applied.append(f"Status: {attendance_status}")

    records = query.order_by(Attendance.date.desc()).all()
    if overtime_only:
        records = [r for r in records if r.overtime_hours > 0]
        filters_applied.append("Overtime only")

    rows = [{
        "attendance_id": r.business_id or "", "date": r.date.strftime("%d-%m-%Y") if r.date else "",
        "employee": r.employee.name if r.employee else "",
        "in_time": r.in_time.strftime("%H:%M") if r.in_time else "",
        "out_time": r.out_time.strftime("%H:%M") if r.out_time else "",
        "standard_hours": float(r.standard_hours or 0), "working_hours": r.working_hours,
        "overtime_hours": r.overtime_hours, "status": r.attendance_status, "remarks": r.remarks or "",
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Records", str(len(records))),
        ("Total Working Hours", f"{sum(r.working_hours for r in records):.2f}"),
        ("Total Overtime Hours", f"{sum(r.overtime_hours for r in records):.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Overtime" if overtime_only else "Attendance",
        "title": "OVERTIME REPORT" if overtime_only else "ATTENDANCE REPORT",
        "columns": ["attendance_id", "date", "employee", "in_time", "out_time", "standard_hours",
                    "working_hours", "overtime_hours", "status", "remarks"],
        "headers": ["Attendance ID", "Date", "Employee", "In Time", "Out Time", "Standard Hours",
                    "Working Hours", "Overtime Hours", "Status", "Remarks"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"{'overtime' if overtime_only else 'attendance'}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/leaves.xlsx")
def export_leaves(
    employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own leave records.")
        if not own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own leave records.")
        employee_id = own_employee_id

    query = db.query(Leave).options(selectinload(Leave.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if status:
        query = query.filter(Leave.status == status)
        filters_applied.append(f"Status: {status}")

    records = query.order_by(Leave.start_date.desc()).all()
    rows = [{
        "leave_id": r.business_id or "", "employee": r.employee.name if r.employee else "",
        "leave_type": r.leave_type, "start_date": r.start_date.strftime("%d-%m-%Y") if r.start_date else "",
        "end_date": r.end_date.strftime("%d-%m-%Y") if r.end_date else "", "days": float(r.days or 0),
        "status": r.status, "approved_by": r.approved_by or "", "reason": r.reason or "",
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Requests", str(len(records))),
        ("Total Days", f"{sum(float(r.days or 0) for r in records):.1f}"),
        ("Approved", str(sum(1 for r in records if r.status == "Approved"))),
    ]

    buffer = build_workbook([{
        "sheet_name": "Leave", "title": "LEAVE REPORT",
        "columns": ["leave_id", "employee", "leave_type", "start_date", "end_date", "days", "status", "approved_by", "reason"],
        "headers": ["Leave ID", "Employee", "Type", "Start Date", "End Date", "Days", "Status", "Approved By", "Reason"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"leaves_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/payroll.xlsx")
def export_payroll(
    employee_id: Optional[int] = Query(None), month: Optional[str] = Query(None), year: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Master-only, matching the same require_role("master") gate the
    salary-slip routes themselves already use - this must never be
    reachable by a direct API call from a non-master session, not just
    hidden from the UI."""
    query = db.query(SalarySlip).options(selectinload(SalarySlip.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if month:
        query = query.filter(SalarySlip.month == month)
        filters_applied.append(f"Month: {month}")
    if year:
        query = query.filter(SalarySlip.year == year)
        filters_applied.append(f"Year: {year}")

    records = query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    rows = [{
        "slip_id": r.business_id or "", "employee": r.employee.name if r.employee else "",
        "month": r.month, "year": r.year, "working_days": float(r.working_days or 0),
        "paid_days": float(r.paid_days or 0), "basic": float(r.basic or 0), "da": float(r.da or 0),
        "hra": float(r.hra or 0), "overtime_amount": float(r.overtime_amount or 0),
        "pf_deduction": float(r.pf_deduction or 0), "tds_deduction": float(r.tds_deduction or 0),
        "other_deductions": float(r.other_deductions or 0), "net_salary": float(r.net_salary or 0),
        "status": r.status,
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Slips", str(len(records))),
        ("Total Net Payout", f"Rs {sum(float(r.net_salary or 0) for r in records):,.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Payroll", "title": "PAYROLL REPORT",
        "columns": ["slip_id", "employee", "month", "year", "working_days", "paid_days", "basic", "da", "hra",
                    "overtime_amount", "pf_deduction", "tds_deduction", "other_deductions", "net_salary", "status"],
        "headers": ["Slip ID", "Employee", "Month", "Year", "Working Days", "Paid Days", "Basic", "DA", "HRA",
                    "Overtime", "PF Deduction", "TDS Deduction", "Other Deductions", "Net Salary", "Status"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"payroll_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/salary-slips/{slip_id}.pdf")
def export_salary_slip_pdf(slip_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    if auth.get("role", "user") not in ("master",) and slip.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
    buffer = generate_salary_slip_pdf(slip, db)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="salary-slip-{slip.month}-{slip.year}.pdf"', "Cache-Control": "no-store, private"},
    )


@router.get("/company-holidays.xlsx")
def export_company_holidays(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The actual stored Company Holiday records, in a
    format that round-trips back through the Holiday Import:
    headers alias to the same import columns, Date is written as
    %Y-%m-%d specifically (the one format the import parser accepts -
    this file's other exports use %d-%m-%Y, which would NOT re-import
    correctly), and Type is the same readable 'Holiday'/'Special
    Working Day' text the import expects, not the raw is_working
    boolean. Master can Export -> edit in Excel -> Import to maintain
    holidays, per the spec's own intended workflow."""
    holidays = db.query(CompanyHoliday).order_by(CompanyHoliday.date).all()
    rows = [{
        "date": h.date.strftime("%Y-%m-%d"),
        "name": h.name,
        "type": "Special Working Day" if h.is_working else "Holiday",
        "remarks": h.remarks or "",
    } for h in holidays]
    columns = ["date", "name", "type", "remarks"]
    headers = ["Date", "Holiday Name", "Type", "Remarks"]
    buffer = build_workbook([{"sheet_name": "Company Holidays", "title": "COMPANY HOLIDAYS",
                               "columns": columns, "headers": headers, "rows": rows,
                               "summary": [("Total Holidays", str(len(holidays)))]}])
    return xlsx_response(buffer, f"company-holidays_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")
