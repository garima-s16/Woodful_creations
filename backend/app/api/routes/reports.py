"""Excel and PDF export endpoints. Excel exports use openpyxl (see
app/utils/exporters.py); the order estimate uses reportlab (see
app/utils/pdf_generator.py)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.models.payment import Payment
from app.models.material import Material
from app.models.supplier import Supplier
from app.models.order import Order
from app.models.estimate import Estimate
from app.models.salary_slip import SalarySlip
from app.models.client import Client
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave import Leave
from app.models.salary_slip import SalarySlip
from app.models.daily_task import DailyTask
from app.models.production_job import ProductionJob
from app.models.automation_log import AutomationLog
from app.models.order_comment import OrderComment
from app.models.task_comment import TaskComment
from app.models.project_expense import ProjectExpense
from app.services.order_service import OrderService
from app.utils.exporters import build_workbook
from app.utils.pdf_generator import (
    generate_order_estimate_pdf, generate_estimate_pdf, generate_salary_slip_pdf, generate_invoice_pdf,
    generate_client_pdf, generate_product_pdf,
)

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


def _xlsx_response(buffer, filename: str) -> StreamingResponse:
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, private",
        },
    )


@router.get("/purchases.xlsx")
def export_purchases(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    purchases = db.query(Purchase).options(
        selectinload(Purchase.supplier), selectinload(Purchase.material)
    ).order_by(Purchase.date.desc()).all()
    rows = [{
        "purchase_code": p.purchase_code, "business_id": p.business_id or "",
        "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
        "quantity": float(p.quantity), "unit": p.unit, "rate": float(p.rate),
        "taxable_value": float(p.taxable_value), "gst_percent": float(p.gst_percent),
        "gst_amount": float(p.gst_amount), "invoice_total": float(p.invoice_total),
        "payment_status": p.payment_status,
    } for p in purchases]
    columns = ["purchase_code", "business_id", "date", "supplier", "material", "quantity", "unit", "rate",
               "taxable_value", "gst_percent", "gst_amount", "invoice_total", "payment_status"]
    headers = ["Purchase ID", "Business ID", "Date", "Supplier", "Material", "Quantity", "Unit", "Rate",
               "Taxable Value", "GST %", "GST Amount", "Invoice Total", "Payment Status"]
    buffer = build_workbook([{"sheet_name": "Purchases", "title": "PURCHASE REGISTER",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["taxable_value", "gst_amount", "invoice_total"]}])
    return _xlsx_response(buffer, "purchases.xlsx")


@router.get("/issues.xlsx")
def export_issues(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    issues = db.query(Issue).options(
        selectinload(Issue.order), selectinload(Issue.material)
    ).order_by(Issue.date.desc()).all()
    rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "order": i.order.order_code if i.order else "", "material": i.material.name if i.material else "",
        "quantity_issued": float(i.quantity_issued), "unit": i.unit, "issued_to": i.issued_to,
        "department": i.department, "purpose": i.purpose, "approved_by": i.approved_by,
    } for i in issues]
    columns = ["issue_code", "date", "order", "material", "quantity_issued", "unit",
               "issued_to", "department", "purpose", "approved_by"]
    headers = ["Issue ID", "Date", "Order", "Material", "Quantity Issued", "Unit",
               "Issued To", "Department", "Purpose", "Approved By"]
    buffer = build_workbook([{"sheet_name": "Issues", "title": "MATERIAL ISSUE REGISTER",
                               "columns": columns, "headers": headers, "rows": rows}])
    return _xlsx_response(buffer, "issues.xlsx")


@router.get("/payments.xlsx")
def export_payments(
    order_id: Optional[int] = None, client_id: Optional[int] = None,
    payment_mode: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    query = db.query(Payment)
    filters_applied = []
    if order_id:
        query = query.filter(Payment.order_id == order_id)
        filters_applied.append(f"Order #{order_id}")
    if client_id:
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
        filters_applied.append(f"Client #{client_id}")
    if payment_mode:
        query = query.filter(Payment.payment_mode == payment_mode)
        filters_applied.append(f"Mode: {payment_mode}")
    if start_date:
        query = query.filter(Payment.date >= datetime.fromisoformat(start_date))
        filters_applied.append(f"From {start_date}")
    if end_date:
        query = query.filter(Payment.date <= datetime.fromisoformat(end_date))
        filters_applied.append(f"To {end_date}")

    payments = query.options(
        selectinload(Payment.order).selectinload(Order.client)
    ).order_by(Payment.date.desc()).all()
    rows = [{
        # Per spec section 2A, "Receipt ID" is the 10-character business ID
        # (e.g. A7K92P4XQ1) - receipt_code (RCPT-001) is kept as a secondary
        # human-scannable sequential reference, same distinction used
        # everywhere else business_id coexists with a *_code field.
        "receipt_id": p.business_id or "", "receipt_code": p.receipt_code,
        "payment_reference": p.reference_number or "",
        "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "order": p.order.order_code if p.order else "",
        "client_id": p.order.client.business_id if p.order and p.order.client else "",
        "client": p.order.client.name if p.order and p.order.client else "",
        "project": p.order.project_type if p.order else "",
        "payment_type": p.payment_type, "payment_mode": p.payment_mode, "amount": float(p.amount),
        "received_by": p.received_by or "", "notes": p.remarks or "",
    } for p in payments]
    columns = ["receipt_id", "receipt_code", "payment_reference", "date", "order", "client_id", "client",
               "project", "payment_type", "payment_mode", "amount", "received_by", "notes"]
    headers = ["Receipt ID", "Receipt Code", "Payment Reference", "Date", "Order ID", "Client ID", "Client Name",
               "Project", "Payment Type", "Payment Mode", "Amount", "Received By", "Notes"]

    total_amount = sum(float(p.amount) for p in payments)
    by_mode = {}
    for p in payments:
        by_mode[p.payment_mode] = by_mode.get(p.payment_mode, 0) + float(p.amount)
    summary = [("Total Payments", f"{len(payments)}"), ("Total Amount", f"Rs {total_amount:,.2f}")]
    summary += [(f"  {mode}", f"Rs {amt:,.2f}") for mode, amt in sorted(by_mode.items())]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Payments", "title": "CLIENT PAYMENT REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["amount"], "subtitle": subtitle, "summary": summary,
    }])
    filename = f"payment_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/clients.xlsx")
def export_clients(
    search: Optional[str] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Client Register - the complete client list without opening each
    client individually (P4). `search`/`status` mirror the filters on
    GET /api/clients/ exactly, so "search Mhow -> export only Mhow
    clients" produces the same set the user is already looking at."""
    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Client)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter((Client.name.ilike(like)) | (Client.client_code.ilike(like)) | (Client.phone.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if status:
        query = query.filter(Client.status == status)
        filters_applied.append(f"Status: {status}")

    clients = query.order_by(Client.name).all()
    rows = []
    for c in clients:
        orders = c.orders or []
        latest_order = max(orders, key=lambda o: o.order_date) if orders else None
        row = {
            "client_id": c.business_id or "", "name": c.name, "contact_person": c.contact_person or "",
            "phone": c.phone or "", "email": c.email or "", "address": c.address or "",
            "site_address": c.site_address or "", "city": c.city or "", "gstin": c.gstin or "",
            "project_count": len(orders), "order_count": len(orders),
            "latest_order": latest_order.order_date.strftime("%d-%m-%Y") if latest_order else "",
            "status": c.status, "created_date": c.created_at.strftime("%d-%m-%Y") if c.created_at else "",
        }
        if is_privileged:
            total_order_value = sum((Decimal(o.order_value or 0) for o in orders), Decimal("0"))
            total_paid = sum((Decimal(o.total_received or 0) for o in orders), Decimal("0"))
            outstanding = sum((Decimal(o.balance or 0) for o in orders), Decimal("0"))
            row["total_order_value"] = float(total_order_value)
            row["total_paid"] = float(total_paid)
            row["outstanding"] = float(outstanding)
        rows.append(row)

    columns = ["client_id", "name", "contact_person", "phone", "email", "address", "site_address", "city",
               "gstin", "project_count", "order_count", "latest_order", "status", "created_date"]
    headers = ["Client ID", "Client Name", "Contact Person", "Phone", "Email", "Address", "Site Address", "City",
               "GSTIN", "Project Count", "Order Count", "Latest Order", "Status", "Created Date"]
    total_columns = []
    if is_privileged:
        idx = columns.index("project_count")
        columns[idx:idx] = ["total_order_value", "total_paid", "outstanding"]
        headers[idx:idx] = ["Total Order Value", "Total Paid", "Outstanding"]
        total_columns = ["total_order_value", "total_paid", "outstanding"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Clients", str(len(clients)))]
    if is_privileged:
        summary.append(("Total Order Value", f"Rs {sum(r['total_order_value'] for r in rows):,.2f}"))
        summary.append(("Total Outstanding", f"Rs {sum(r['outstanding'] for r in rows):,.2f}"))

    buffer = build_workbook([{
        "sheet_name": "Clients", "title": "CLIENT REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": total_columns,
        "subtitle": subtitle, "summary": summary,
    }])
    filename = f"client_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/products.xlsx")
def export_products(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Product Master export (Family 104 section 40). search/category/
    is_active mirror GET /api/products/ exactly, so the export matches
    whatever the person is currently looking at on the Products list."""
    from app.models.product import Product

    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Product)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.product_code.ilike(like),
                                  Product.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Product.category == category)
        filters_applied.append(f"Category: {category}")
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
        filters_applied.append(f"Status: {'Active' if is_active else 'Inactive'}")

    products = query.order_by(Product.name).all()
    rows = []
    for p in products:
        row = {
            "product_id": p.business_id or "", "product_code": p.product_code, "name": p.name,
            "type": p.product_type, "category": p.category or "", "subcategory": p.subcategory or "",
            "unit": p.unit, "selling_price": float(p.selling_price) if p.selling_price is not None else None,
            "gst_percent": float(p.gst_percent) if p.gst_percent is not None else None,
            "status": "Active" if p.is_active else "Inactive",
        }
        if is_privileged:
            row["cost_price"] = float(p.cost_price) if p.cost_price is not None else None
            row["margin"] = p.margin
        rows.append(row)

    columns = ["product_id", "product_code", "name", "type", "category", "subcategory", "unit",
               "selling_price", "gst_percent", "status"]
    headers = ["Product ID", "Product Code", "Product Name", "Type", "Category", "Subcategory", "Unit",
               "Default Rate", "GST %", "Status"]
    if is_privileged:
        columns += ["cost_price", "margin"]
        headers += ["Cost Price", "Margin"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Products", "title": "PRODUCT MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Products", str(len(products)))],
    }])
    filename = f"product_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


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
        "status": e.status, "manager": e.manager or "", "address": e.address or "",
    } for e in employees]
    columns = ["employee_id", "name", "designation", "department", "phone", "email",
               "joining_date", "status", "manager", "address"]
    headers = ["Employee ID", "Employee Name", "Designation", "Department", "Phone", "Email",
               "Joining Date", "Employment Status", "Manager/Supervisor", "Address"]

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
    return _xlsx_response(buffer, filename)


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
    return _xlsx_response(buffer, filename)


@router.get("/leaves.xlsx")
def export_leaves(
    employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
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
    return _xlsx_response(buffer, filename)


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
    return _xlsx_response(buffer, filename)


@router.get("/estimates.xlsx")
def export_estimates(
    client_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    query = db.query(Estimate).options(selectinload(Estimate.client))
    filters_applied = []
    if client_id:
        query = query.filter(Estimate.client_id == client_id)
        client = db.query(Client).filter(Client.id == client_id).first()
        filters_applied.append(f"Client: {client.name if client else client_id}")
    if status:
        query = query.filter(Estimate.status == status)
        filters_applied.append(f"Status: {status}")

    estimates = query.order_by(Estimate.created_at.desc()).all()
    rows = [{
        "estimate_id": e.business_id or "", "estimate_code": e.estimate_code,
        "client": e.client.name if e.client else "", "version": e.version,
        "material_cost": float(e.material_cost or 0), "labor_cost": float(e.labor_cost or 0),
        "discount": float(e.discount or 0), "tax_percent": float(e.tax_percent or 0),
        "tax_amount": float(e.tax_amount or 0), "total_cost": float(e.total_cost or 0),
        "status": e.status, "converted_to_order": "Yes" if e.order_id else "No",
        "valid_until": e.valid_until.strftime("%d-%m-%Y") if e.valid_until else "",
    } for e in estimates]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Estimates", str(len(estimates))),
        ("Approved", str(sum(1 for e in estimates if e.status == "approved"))),
        ("Converted to Orders", str(sum(1 for e in estimates if e.order_id))),
        ("Total Value", f"Rs {sum(float(e.total_cost or 0) for e in estimates):,.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Estimates", "title": "ESTIMATES & QUOTATIONS REPORT",
        "columns": ["estimate_id", "estimate_code", "client", "version", "material_cost", "labor_cost",
                    "discount", "tax_percent", "tax_amount", "total_cost", "status", "converted_to_order", "valid_until"],
        "headers": ["Estimate ID", "Code", "Client", "Version", "Material Cost", "Labor Cost",
                    "Discount", "Tax %", "Tax Amount", "Total Cost", "Status", "Converted to Order", "Valid Until"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"estimates_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/production.xlsx")
def export_production(
    employee_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
    order_id: Optional[int] = Query(None), stage: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """One flexible, filterable endpoint covering "Production Jobs",
    "Daily/Weekly Production" (via date_from/date_to), and
    "Machine/Operator Work" (via machine/employee_id) - all genuinely
    the same underlying ProductionJob data with a different filter
    applied, matching the export_tasks precedent rather than
    proliferating near-duplicate routes for each named variant."""
    query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        query = query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Operator: {employee.name if employee else employee_id}")
    if machine:
        query = query.filter(ProductionJob.machine == machine)
        filters_applied.append(f"Machine: {machine}")
    if order_id:
        query = query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if stage:
        query = query.filter(ProductionJob.stage == stage)
        filters_applied.append(f"Stage: {stage}")
    if date_from:
        query = query.filter(ProductionJob.date >= date_from)
        filters_applied.append(f"From: {date_from.strftime('%d-%m-%Y')}")
    if date_to:
        query = query.filter(ProductionJob.date <= date_to)
        filters_applied.append(f"To: {date_to.strftime('%d-%m-%Y')}")

    jobs = query.order_by(ProductionJob.date.desc()).all()
    rows = [{
        "job_id": j.business_id or "", "date": j.date.strftime("%d-%m-%Y") if j.date else "",
        "operator": j.employee.name if j.employee else "", "order": j.order.order_code if j.order else "",
        "machine": j.machine or "", "stage": j.stage or "", "operation": j.operation or "",
        "planned_qty": j.planned_qty, "completed_qty": j.completed_qty, "status": j.status,
        "completion_date": j.completion_date.strftime("%d-%m-%Y") if j.completion_date else "",
        "remarks": j.remarks or "",
    } for j in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Jobs", str(len(jobs))),
        ("Completed", str(sum(1 for j in jobs if j.status == "Completed"))),
        ("Total Planned Qty", str(sum(j.planned_qty for j in jobs))),
        ("Total Completed Qty", str(sum(j.completed_qty for j in jobs))),
    ]

    buffer = build_workbook([{
        "sheet_name": "Production", "title": "PRODUCTION REPORT",
        "columns": ["job_id", "date", "operator", "order", "machine", "stage", "operation",
                    "planned_qty", "completed_qty", "status", "completion_date", "remarks"],
        "headers": ["Job ID", "Date", "Operator", "Order", "Machine", "Stage", "Operation",
                    "Planned Qty", "Completed Qty", "Status", "Completion Date", "Remarks"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/tasks.xlsx")
def export_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Tasks & Production export - no financial fields exist on either
    model, so no role-based redaction is needed, matching "everyone can
    view tasks" for the Tasks sheet. employee_id covers "Employee-wise
    Tasks Excel", order_id covers "Project Tasks Excel" - one flexible,
    filterable endpoint rather than three separate routes for what's
    the same underlying data with a different filter applied."""
    task_query = db.query(DailyTask).options(selectinload(DailyTask.employee), selectinload(DailyTask.order))
    job_query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        task_query = task_query.filter(DailyTask.employee_id == employee_id)
        job_query = job_query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if order_id:
        task_query = task_query.filter(DailyTask.order_id == order_id)
        job_query = job_query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")

    tasks = task_query.order_by(DailyTask.date.desc()).all()
    task_rows = [{
        "task_id": t.business_id or "", "date": t.date.strftime("%d-%m-%Y") if t.date else "",
        "employee": t.employee.name if t.employee else "", "task": t.task_description,
        "order": t.order.order_code if t.order else "", "priority": t.priority or "",
        "status": t.status, "completion_percent": t.completion_percent,
        "delay_reason": t.delay_reason or "", "remarks": t.remarks or "",
    } for t in tasks]

    jobs = job_query.order_by(ProductionJob.date.desc()).all()
    job_rows = [{
        "job_id": p.business_id or "", "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "employee": p.employee.name if p.employee else "", "order": p.order.order_code if p.order else "",
        "operation": p.operation or "", "planned_qty": p.planned_qty, "completed_qty": p.completed_qty,
        "status": p.status,
    } for p in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([
        {"sheet_name": "Tasks", "title": "STAFF TASKS",
         "columns": ["task_id", "date", "employee", "task", "order", "priority", "status",
                     "completion_percent", "delay_reason", "remarks"],
         "headers": ["Task ID", "Date", "Employee", "Task", "Order", "Priority", "Status",
                     "Completion %", "Delay Reason", "Remarks"],
         "rows": task_rows, "subtitle": subtitle},
        {"sheet_name": "Production", "title": "PRODUCTION JOBS",
         "columns": ["job_id", "date", "employee", "order", "operation", "planned_qty", "completed_qty", "status"],
         "headers": ["Job ID", "Date", "Operator", "Order", "Operation", "Planned Qty", "Completed Qty", "Status"],
         "rows": job_rows, "subtitle": subtitle},
    ])
    filename = f"tasks_production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/order-profitability.xlsx")
def export_order_profitability(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    rows = []
    for o in orders:
        p = OrderService.profitability(db, o)
        rows.append({
            "order_id": p["order_id"], "business_id": p["business_id"], "client": p["client"], "project_type": p["project_type"],
            "order_value": p["order_value"], "total_received": p["total_received"],
            "pending_payment": p["pending_payment"], "project_expenses": p["project_expenses"],
            "material_cost": p["material_cost"],
            "estimated_gross_profit": p["estimated_gross_profit"],
            "gross_margin_percent": p["gross_margin_percent"], "status": p["status"],
        })
    columns = ["order_id", "business_id", "client", "project_type", "order_value", "total_received",
               "pending_payment", "project_expenses", "material_cost", "estimated_gross_profit",
               "gross_margin_percent", "status"]
    headers = ["Order ID", "Business ID", "Client", "Project Type", "Order Value", "Total Received",
               "Pending Payment", "Project Expenses", "Material Cost", "Estimated Gross Profit",
               "Gross Margin %", "Status"]
    buffer = build_workbook([{"sheet_name": "Order Profitability", "title": "ORDER-WISE PROFITABILITY REPORT",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["order_value", "total_received", "pending_payment",
                                                  "project_expenses", "material_cost", "estimated_gross_profit"]}])
    return _xlsx_response(buffer, "order-profitability.xlsx")


@router.get("/orders.xlsx")
def export_orders(
    status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Family 12 - Sales/Orders Register export. Mirrors GET /api/orders/'s
    status/client_id filters. Financial columns (order value, received,
    balance) are master-only, exactly matching the redaction
    _serialize_orders already applies on-screen for a non-master viewer -
    export inherits the same scope as the list view, never more."""
    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Order).options(selectinload(Order.client))
    filters_applied = []
    if status:
        query = query.filter(Order.project_status == status)
        filters_applied.append(f"Status: {status}")
    if client_id:
        query = query.filter(Order.client_id == client_id)
        client_obj = db.query(Client).filter(Client.id == client_id).first()
        filters_applied.append(f"Client: {client_obj.name if client_obj else client_id}")

    orders = query.order_by(Order.order_date.desc()).all()
    rows = []
    for o in orders:
        row = {
            "order_id": o.business_id or "", "order_code": o.order_code,
            "client": o.client.name if o.client else "", "project_type": o.project_type or "",
            "order_date": o.order_date.strftime("%d-%m-%Y") if o.order_date else "",
            "delivery_date": o.delivery_date.strftime("%d-%m-%Y") if o.delivery_date else "",
            "status": o.project_status, "progress_percent": o.progress_percent,
        }
        if is_privileged:
            row["order_value"] = float(o.order_value or 0)
            row["total_received"] = float(o.total_received or 0)
            row["balance"] = float(o.balance or 0)
        rows.append(row)

    columns = ["order_id", "order_code", "client", "project_type", "order_date", "delivery_date",
               "status", "progress_percent"]
    headers = ["Order ID", "Order Code", "Client", "Project Type", "Order Date", "Delivery Date",
               "Status", "Progress %"]
    total_columns = []
    if is_privileged:
        columns[6:6] = ["order_value", "total_received", "balance"]
        headers[6:6] = ["Order Value", "Total Received", "Balance"]
        total_columns = ["order_value", "total_received", "balance"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Orders", str(len(orders)))]
    if is_privileged:
        summary.append(("Total Order Value", f"Rs {sum(r['order_value'] for r in rows):,.2f}"))
        summary.append(("Total Outstanding", f"Rs {sum(r['balance'] for r in rows):,.2f}"))

    buffer = build_workbook([{
        "sheet_name": "Orders", "title": "SALES / ORDERS REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": total_columns, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"orders_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/project-expenses.xlsx")
def export_project_expenses(
    order_id: Optional[int] = Query(None), category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Family 12 - Expense Register export. Master-only, matching
    project_expenses.py's own require_role("master") gate - every field
    on ProjectExpense is financial, so there is no partial/redacted view."""
    query = db.query(ProjectExpense).options(selectinload(ProjectExpense.order))
    filters_applied = []
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if category:
        query = query.filter(ProjectExpense.category == category)
        filters_applied.append(f"Category: {category}")
    if start_date:
        query = query.filter(ProjectExpense.date >= datetime.fromisoformat(start_date))
        filters_applied.append(f"From {start_date}")
    if end_date:
        query = query.filter(ProjectExpense.date <= datetime.fromisoformat(end_date))
        filters_applied.append(f"To {end_date}")

    expenses = query.order_by(ProjectExpense.date.desc()).all()
    rows = [{
        "expense_id": e.business_id or "", "expense_code": e.expense_code,
        "date": e.date.strftime("%d-%m-%Y") if e.date else "",
        "order": e.order.order_code if e.order else "", "category": e.category,
        "description": e.description or "", "paid_to": e.paid_to or "",
        "amount": float(e.amount or 0), "approved_by": e.approved_by or "",
    } for e in expenses]
    columns = ["expense_id", "expense_code", "date", "order", "category", "description",
               "paid_to", "amount", "approved_by"]
    headers = ["Expense ID", "Expense Code", "Date", "Order", "Category", "Description",
               "Paid To", "Amount", "Approved By"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    by_category = {}
    for e in expenses:
        by_category[e.category or "Uncategorized"] = by_category.get(e.category or "Uncategorized", 0) + float(e.amount or 0)
    summary = [("Total Expenses", str(len(expenses))), ("Total Amount", f"Rs {sum(float(e.amount or 0) for e in expenses):,.2f}")]
    summary += [(f"  {cat}", f"Rs {amt:,.2f}") for cat, amt in sorted(by_category.items())]

    buffer = build_workbook([{
        "sheet_name": "Expenses", "title": "PROJECT EXPENSE REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["amount"], "subtitle": subtitle, "summary": summary,
    }])
    filename = f"expense_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(buffer, filename)


@router.get("/stock-dashboard.xlsx")
def export_stock_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    materials = db.query(Material).options(selectinload(Material.primary_supplier)).all()
    suppliers = db.query(Supplier).all()
    issues = db.query(Issue).options(selectinload(Issue.material)).order_by(Issue.date.desc()).all()

    material_columns = ["material_id", "business_id", "name", "category", "brand_grade", "thickness_size", "unit",
                         "opening_stock", "total_purchased", "total_issued", "current_stock",
                         "minimum_stock", "stock_status", "primary_supplier", "location"]
    material_headers = ["Material ID", "Business ID", "Name", "Category", "Brand/Grade", "Thickness/Size", "Unit",
                         "Opening Stock", "Total Purchased", "Total Issued", "Current Stock",
                         "Minimum Stock", "Stock Status", "Primary Supplier", "Location"]
    if is_privileged:
        # Financial columns only exist in the privileged version - not
        # present-but-blank in the employee version, genuinely absent.
        material_columns[13:13] = ["average_rate", "stock_value"]
        material_headers[13:13] = ["Average Rate", "Stock Value"]

    material_rows = [{
        "material_id": m.material_code, "business_id": m.business_id or "", "name": m.name, "category": m.category,
        "brand_grade": m.brand_grade, "thickness_size": m.thickness_size, "unit": m.unit,
        "opening_stock": m.opening_stock, "total_purchased": m.total_purchased,
        "total_issued": m.total_issued, "current_stock": m.current_stock,
        "minimum_stock": m.minimum_stock, "stock_status": m.stock_status,
        **({"average_rate": float(m.average_rate), "stock_value": m.stock_value} if is_privileged else {}),
        "primary_supplier": m.primary_supplier.name if m.primary_supplier else "",
        "location": m.location,
    } for m in materials]

    issue_rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "material": i.material.name if i.material else "", "quantity_issued": float(i.quantity_issued),
        "issued_to": i.issued_to, "department": i.department,
    } for i in issues]

    supplier_rows = [{
        "supplier_code": s.supplier_code, "business_id": s.business_id or "", "name": s.name, "category": s.category,
        "contact_person": s.contact_person, "phone": s.phone, "payment_terms": s.payment_terms,
    } for s in suppliers]

    sheets = []
    if is_privileged:
        purchases = db.query(Purchase).options(
            selectinload(Purchase.supplier), selectinload(Purchase.material)
        ).order_by(Purchase.date.desc()).all()
        dashboard_rows = [{
            "metric": "Total Stock Value", "value": round(sum(m.stock_value for m in materials), 2),
        }, {
            "metric": "Low Stock Items", "value": len([m for m in materials if 0 < m.current_stock <= m.minimum_stock]),
        }, {
            "metric": "Out of Stock Items", "value": len([m for m in materials if m.current_stock <= 0]),
        }, {
            "metric": "Purchase Value", "value": round(sum(float(p.invoice_total or 0) for p in purchases), 2),
        }]
        purchase_rows = [{
            "purchase_code": p.purchase_code, "business_id": p.business_id or "",
            "date": p.date.strftime("%d-%m-%Y") if p.date else "",
            "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
            "quantity": float(p.quantity), "invoice_total": float(p.invoice_total), "payment_status": p.payment_status,
        } for p in purchases]
        sheets.append({"sheet_name": "Dashboard", "title": "STOCK DASHBOARD", "columns": ["metric", "value"],
                        "headers": ["Metric", "Value"], "rows": dashboard_rows})

    sheets.append({"sheet_name": "Material Master", "title": "LIVE MATERIAL STOCK MASTER",
                    "columns": material_columns, "headers": material_headers, "rows": material_rows,
                    "total_columns": ["stock_value"] if is_privileged else []})

    if is_privileged:
        sheets.append({"sheet_name": "Purchases", "title": "STOCK IN - PURCHASE REGISTER",
                        "columns": ["purchase_code", "business_id", "date", "supplier", "material", "quantity", "invoice_total", "payment_status"],
                        "headers": ["Purchase ID", "Business ID", "Date", "Supplier", "Material", "Quantity", "Invoice Total", "Payment Status"],
                        "rows": purchase_rows})

    sheets.append({"sheet_name": "Issues", "title": "STOCK OUT - MATERIAL ISSUE REGISTER",
                    "columns": ["issue_code", "date", "material", "quantity_issued", "issued_to", "department"],
                    "headers": ["Issue ID", "Date", "Material", "Quantity Issued", "Issued To", "Department"],
                    "rows": issue_rows})
    sheets.append({"sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
                    "columns": ["supplier_code", "business_id", "name", "category", "contact_person", "phone", "payment_terms"],
                    "headers": ["Supplier ID", "Business ID", "Supplier Name", "Category", "Contact Person", "Phone", "Payment Terms"],
                    "rows": supplier_rows})

    buffer = build_workbook(sheets)
    return _xlsx_response(buffer, "stock-dashboard.xlsx")


@router.get("/orders/{order_id}/estimate.pdf")
def export_order_estimate_pdf(order_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """Family 12 gap fix: this PDF includes order_value/total_received -
    the exact fields _serialize_orders() nulls for non-master in the
    JSON API (orders.py). It was previously exportable by any
    authenticated role via get_current_user, letting a USER bypass the
    redaction entirely. Master-only now, matching invoice.pdf below."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    buffer = generate_order_estimate_pdf(order)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{order.order_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@router.get("/clients/{client_id}/profile.pdf")
def export_client_pdf(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Client profile PDF (Family 103 section 6) - available to any
    authenticated role (client contact info isn't the financial data
    that's restricted elsewhere); the sales-summary figures inside
    still only render for whoever the client relationship allows -
    same underlying Client/Order records the rest of the app uses."""
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    buffer = generate_client_pdf(client)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="client-{client.client_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@router.get("/products/{product_id}/product.pdf")
def export_product_pdf(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    from app.models.product import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    buffer = generate_product_pdf(product)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="product-{product.product_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@router.get("/estimates/{estimate_id}/quote.pdf")
def export_estimate_quote_pdf(estimate_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """Family 12 gap fix: this PDF includes per-line-item rate/amount -
    the same line-item pricing test_estimate_financial_rbac.py already
    proves is nulled for non-master via the JSON API. It was previously
    exportable by any authenticated role via get_current_user. Master-only
    now, matching every other estimate-mutation endpoint in estimates.py."""
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    buffer = generate_estimate_pdf(estimate)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{estimate.estimate_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@router.get("/orders/{order_id}/invoice.pdf")
def export_order_invoice_pdf(order_id: int, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.date).all()
    buffer = generate_invoice_pdf(order, payments)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{order.order_code}.pdf"', "Cache-Control": "no-store, private"},
    )


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


@router.get("/automation-log.xlsx")
def export_automation_log(rule_key: Optional[str] = None, status: Optional[str] = None,
                           db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 13 - the automation audit trail as a downloadable report.
    Reuses this module's existing Excel infrastructure (build_workbook /
    write_sheet) rather than a separate export mechanism - same
    formatting, same formula-injection sanitization, as every other
    report here. Master-only, same as GET /api/automation/logs and
    /api/audit-logs."""
    query = db.query(AutomationLog)
    if rule_key:
        query = query.filter(AutomationLog.rule_key == rule_key)
    if status:
        query = query.filter(AutomationLog.status == status)
    logs = query.order_by(AutomationLog.created_at.desc()).limit(2000).all()
    rows = [{
        "created_at": log.created_at.strftime("%d-%m-%Y %H:%M") if log.created_at else "",
        "rule_key": log.rule_key, "trigger_event": log.trigger_event, "status": log.status,
        "action_taken": log.action_taken, "condition_summary": log.condition_summary,
        "related_entity_type": log.related_entity_type or "", "related_entity_id": log.related_entity_id or "",
        "error_message": log.error_message or "",
    } for log in logs]
    columns = ["created_at", "rule_key", "trigger_event", "status", "action_taken",
               "condition_summary", "related_entity_type", "related_entity_id", "error_message"]
    headers = ["When", "Rule", "Trigger", "Status", "Action Taken",
               "Condition", "Entity Type", "Entity ID", "Error"]
    buffer = build_workbook([{"sheet_name": "Automation Log", "title": "AUTOMATION AUDIT TRAIL",
                               "columns": columns, "headers": headers, "rows": rows}])
    return _xlsx_response(buffer, f"automation-log_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")
