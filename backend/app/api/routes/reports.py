"""Excel and PDF export endpoints. Excel exports use openpyxl (see
app/utils/exporters.py); the order estimate uses reportlab (see
app/utils/pdf_generator.py)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
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
from app.services.order_service import OrderService
from app.utils.exporters import build_workbook
from app.utils.pdf_generator import generate_order_estimate_pdf, generate_estimate_pdf, generate_salary_slip_pdf, generate_invoice_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _xlsx_response(buffer, filename: str) -> StreamingResponse:
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/purchases.xlsx")
def export_purchases(db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    purchases = db.query(Purchase).order_by(Purchase.date.desc()).all()
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
    issues = db.query(Issue).order_by(Issue.date.desc()).all()
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
    db: Session = Depends(get_db), auth=Depends(require_role("master", "manager")),
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

    payments = query.order_by(Payment.date.desc()).all()
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
        total_order_value = sum((Decimal(o.order_value or 0) for o in orders), Decimal("0"))
        total_paid = sum((Decimal(o.total_received or 0) for o in orders), Decimal("0"))
        outstanding = sum((Decimal(o.balance or 0) for o in orders), Decimal("0"))
        latest_order = max(orders, key=lambda o: o.order_date) if orders else None
        rows.append({
            "client_id": c.business_id or "", "name": c.name, "phone": c.phone or "",
            "email": c.email or "", "address": c.address or "", "city": c.city or "",
            "project_count": len(orders), "order_count": len(orders),
            "total_order_value": float(total_order_value), "total_paid": float(total_paid),
            "outstanding": float(outstanding),
            "latest_order": latest_order.order_date.strftime("%d-%m-%Y") if latest_order else "",
            "status": c.status, "created_date": c.created_at.strftime("%d-%m-%Y") if c.created_at else "",
        })
    columns = ["client_id", "name", "phone", "email", "address", "city", "project_count", "order_count",
               "total_order_value", "total_paid", "outstanding", "latest_order", "status", "created_date"]
    headers = ["Client ID", "Client Name", "Phone", "Email", "Address", "City", "Project Count", "Order Count",
               "Total Order Value", "Total Paid", "Outstanding", "Latest Order", "Status", "Created Date"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Clients", str(len(clients))),
        ("Total Order Value", f"Rs {sum(r['total_order_value'] for r in rows):,.2f}"),
        ("Total Outstanding", f"Rs {sum(r['outstanding'] for r in rows):,.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Clients", "title": "CLIENT REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["total_order_value", "total_paid", "outstanding"],
        "subtitle": subtitle, "summary": summary,
    }])
    filename = f"client_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
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
    return _xlsx_response(buffer, filename)


@router.get("/order-profitability.xlsx")
def export_order_profitability(db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    rows = []
    for o in orders:
        p = OrderService.profitability(db, o)
        rows.append({
            "order_id": p["order_id"], "business_id": p["business_id"], "client": p["client"], "project_type": p["project_type"],
            "order_value": p["order_value"], "total_received": p["total_received"],
            "pending_payment": p["pending_payment"], "project_expenses": p["project_expenses"],
            "estimated_gross_profit": p["estimated_gross_profit"],
            "gross_margin_percent": p["gross_margin_percent"], "status": p["status"],
        })
    columns = ["order_id", "business_id", "client", "project_type", "order_value", "total_received",
               "pending_payment", "project_expenses", "estimated_gross_profit",
               "gross_margin_percent", "status"]
    headers = ["Order ID", "Business ID", "Client", "Project Type", "Order Value", "Total Received",
               "Pending Payment", "Project Expenses", "Estimated Gross Profit",
               "Gross Margin %", "Status"]
    buffer = build_workbook([{"sheet_name": "Order Profitability", "title": "ORDER-WISE PROFITABILITY REPORT",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["order_value", "total_received", "pending_payment",
                                                  "project_expenses", "estimated_gross_profit"]}])
    return _xlsx_response(buffer, "order-profitability.xlsx")


@router.get("/stock-dashboard.xlsx")
def export_stock_dashboard(db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    materials = db.query(Material).all()
    suppliers = db.query(Supplier).all()
    purchases = db.query(Purchase).order_by(Purchase.date.desc()).all()
    issues = db.query(Issue).order_by(Issue.date.desc()).all()

    dashboard_rows = [{
        "metric": "Total Stock Value", "value": round(sum(m.stock_value for m in materials), 2),
    }, {
        "metric": "Low Stock Items", "value": len([m for m in materials if 0 < m.current_stock <= m.minimum_stock]),
    }, {
        "metric": "Out of Stock Items", "value": len([m for m in materials if m.current_stock <= 0]),
    }, {
        "metric": "Purchase Value", "value": round(sum(float(p.invoice_total or 0) for p in purchases), 2),
    }]

    material_rows = [{
        "material_id": m.material_code, "business_id": m.business_id or "", "name": m.name, "category": m.category,
        "brand_grade": m.brand_grade, "thickness_size": m.thickness_size, "unit": m.unit,
        "opening_stock": m.opening_stock, "total_purchased": m.total_purchased,
        "total_issued": m.total_issued, "current_stock": m.current_stock,
        "minimum_stock": m.minimum_stock, "stock_status": m.stock_status,
        "average_rate": float(m.average_rate), "stock_value": m.stock_value,
        "primary_supplier": m.primary_supplier.name if m.primary_supplier else "",
        "location": m.location,
    } for m in materials]

    purchase_rows = [{
        "purchase_code": p.purchase_code, "business_id": p.business_id or "",
        "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
        "quantity": float(p.quantity), "invoice_total": float(p.invoice_total), "payment_status": p.payment_status,
    } for p in purchases]

    issue_rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "material": i.material.name if i.material else "", "quantity_issued": float(i.quantity_issued),
        "issued_to": i.issued_to, "department": i.department,
    } for i in issues]

    supplier_rows = [{
        "supplier_code": s.supplier_code, "business_id": s.business_id or "", "name": s.name, "category": s.category,
        "contact_person": s.contact_person, "phone": s.phone, "payment_terms": s.payment_terms,
    } for s in suppliers]

    sheets = [
        {"sheet_name": "Dashboard", "title": "STOCK DASHBOARD", "columns": ["metric", "value"],
         "headers": ["Metric", "Value"], "rows": dashboard_rows},
        {"sheet_name": "Material Master", "title": "LIVE MATERIAL STOCK MASTER",
         "columns": ["material_id", "business_id", "name", "category", "brand_grade", "thickness_size", "unit",
                     "opening_stock", "total_purchased", "total_issued", "current_stock",
                     "minimum_stock", "stock_status", "average_rate", "stock_value",
                     "primary_supplier", "location"],
         "headers": ["Material ID", "Business ID", "Name", "Category", "Brand/Grade", "Thickness/Size", "Unit",
                     "Opening Stock", "Total Purchased", "Total Issued", "Current Stock",
                     "Minimum Stock", "Stock Status", "Average Rate", "Stock Value",
                     "Primary Supplier", "Location"],
         "rows": material_rows, "total_columns": ["stock_value"]},
        {"sheet_name": "Purchases", "title": "STOCK IN - PURCHASE REGISTER",
         "columns": ["purchase_code", "business_id", "date", "supplier", "material", "quantity", "invoice_total", "payment_status"],
         "headers": ["Purchase ID", "Business ID", "Date", "Supplier", "Material", "Quantity", "Invoice Total", "Payment Status"],
         "rows": purchase_rows},
        {"sheet_name": "Issues", "title": "STOCK OUT - MATERIAL ISSUE REGISTER",
         "columns": ["issue_code", "date", "material", "quantity_issued", "issued_to", "department"],
         "headers": ["Issue ID", "Date", "Material", "Quantity Issued", "Issued To", "Department"],
         "rows": issue_rows},
        {"sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
         "columns": ["supplier_code", "business_id", "name", "category", "contact_person", "phone", "payment_terms"],
         "headers": ["Supplier ID", "Business ID", "Supplier Name", "Category", "Contact Person", "Phone", "Payment Terms"],
         "rows": supplier_rows},
    ]
    buffer = build_workbook(sheets)
    return _xlsx_response(buffer, "stock-dashboard.xlsx")


@router.get("/orders/{order_id}/estimate.pdf")
def export_order_estimate_pdf(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    buffer = generate_order_estimate_pdf(order)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{order.order_code}.pdf"'},
    )


@router.get("/estimates/{estimate_id}/quote.pdf")
def export_estimate_quote_pdf(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    buffer = generate_estimate_pdf(estimate)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{estimate.estimate_code}.pdf"'},
    )


@router.get("/orders/{order_id}/invoice.pdf")
def export_order_invoice_pdf(order_id: int, db: Session = Depends(get_db),
                              auth=Depends(require_role("master", "manager"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.date).all()
    buffer = generate_invoice_pdf(order, payments)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{order.order_code}.pdf"'},
    )


@router.get("/salary-slips/{slip_id}.pdf")
def export_salary_slip_pdf(slip_id: int, db: Session = Depends(get_db),
                            auth=Depends(require_role("master", "manager"))):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    buffer = generate_salary_slip_pdf(slip)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="salary-slip-{slip.month}-{slip.year}.pdf"'},
    )
