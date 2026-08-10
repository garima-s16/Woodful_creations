"""Excel and PDF export endpoints. Excel exports use openpyxl (see
app/utils/exporters.py); the order estimate uses reportlab (see
app/utils/pdf_generator.py)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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
        "purchase_code": p.purchase_code, "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
        "quantity": float(p.quantity), "unit": p.unit, "rate": float(p.rate),
        "taxable_value": float(p.taxable_value), "gst_percent": float(p.gst_percent),
        "gst_amount": float(p.gst_amount), "invoice_total": float(p.invoice_total),
        "payment_status": p.payment_status,
    } for p in purchases]
    columns = ["purchase_code", "date", "supplier", "material", "quantity", "unit", "rate",
               "taxable_value", "gst_percent", "gst_amount", "invoice_total", "payment_status"]
    headers = ["Purchase ID", "Date", "Supplier", "Material", "Quantity", "Unit", "Rate",
               "Taxable Value", "GST %", "GST Amount", "Invoice Total", "Payment Status"]
    buffer = build_workbook([{"sheet_name": "Purchases", "title": "PURCHASE REGISTER",
                               "columns": columns, "headers": headers, "rows": rows}])
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
def export_payments(db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    payments = db.query(Payment).order_by(Payment.date.desc()).all()
    rows = [{
        "receipt_code": p.receipt_code, "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "order": p.order.order_code if p.order else "", "client": p.order.client.name if p.order and p.order.client else "",
        "payment_type": p.payment_type, "payment_mode": p.payment_mode, "amount": float(p.amount),
        "reference_number": p.reference_number, "received_by": p.received_by,
    } for p in payments]
    columns = ["receipt_code", "date", "order", "client", "payment_type", "payment_mode",
               "amount", "reference_number", "received_by"]
    headers = ["Receipt ID", "Date", "Order ID", "Client Name", "Payment Type", "Payment Mode",
               "Amount", "Reference No.", "Received By"]
    buffer = build_workbook([{"sheet_name": "Payments", "title": "CLIENT PAYMENT REGISTER",
                               "columns": columns, "headers": headers, "rows": rows}])
    return _xlsx_response(buffer, "payments.xlsx")


@router.get("/order-profitability.xlsx")
def export_order_profitability(db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    rows = []
    for o in orders:
        p = OrderService.profitability(db, o)
        rows.append({
            "order_id": p["order_id"], "client": p["client"], "project_type": p["project_type"],
            "order_value": p["order_value"], "total_received": p["total_received"],
            "pending_payment": p["pending_payment"], "project_expenses": p["project_expenses"],
            "estimated_gross_profit": p["estimated_gross_profit"],
            "gross_margin_percent": p["gross_margin_percent"], "status": p["status"],
        })
    columns = ["order_id", "client", "project_type", "order_value", "total_received",
               "pending_payment", "project_expenses", "estimated_gross_profit",
               "gross_margin_percent", "status"]
    headers = ["Order ID", "Client", "Project Type", "Order Value", "Total Received",
               "Pending Payment", "Project Expenses", "Estimated Gross Profit",
               "Gross Margin %", "Status"]
    buffer = build_workbook([{"sheet_name": "Order Profitability", "title": "ORDER-WISE PROFITABILITY REPORT",
                               "columns": columns, "headers": headers, "rows": rows}])
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
        "material_id": m.material_code, "name": m.name, "category": m.category,
        "brand_grade": m.brand_grade, "thickness_size": m.thickness_size, "unit": m.unit,
        "opening_stock": m.opening_stock, "total_purchased": m.total_purchased,
        "total_issued": m.total_issued, "current_stock": m.current_stock,
        "minimum_stock": m.minimum_stock, "stock_status": m.stock_status,
        "average_rate": float(m.average_rate), "stock_value": m.stock_value,
        "primary_supplier": m.primary_supplier.name if m.primary_supplier else "",
        "location": m.location,
    } for m in materials]

    purchase_rows = [{
        "purchase_code": p.purchase_code, "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
        "quantity": float(p.quantity), "invoice_total": float(p.invoice_total), "payment_status": p.payment_status,
    } for p in purchases]

    issue_rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "material": i.material.name if i.material else "", "quantity_issued": float(i.quantity_issued),
        "issued_to": i.issued_to, "department": i.department,
    } for i in issues]

    supplier_rows = [{
        "supplier_code": s.supplier_code, "name": s.name, "category": s.category,
        "contact_person": s.contact_person, "phone": s.phone, "payment_terms": s.payment_terms,
    } for s in suppliers]

    sheets = [
        {"sheet_name": "Dashboard", "title": "STOCK DASHBOARD", "columns": ["metric", "value"],
         "headers": ["Metric", "Value"], "rows": dashboard_rows},
        {"sheet_name": "Material Master", "title": "LIVE MATERIAL STOCK MASTER",
         "columns": ["material_id", "name", "category", "brand_grade", "thickness_size", "unit",
                     "opening_stock", "total_purchased", "total_issued", "current_stock",
                     "minimum_stock", "stock_status", "average_rate", "stock_value",
                     "primary_supplier", "location"],
         "headers": ["Material ID", "Name", "Category", "Brand/Grade", "Thickness/Size", "Unit",
                     "Opening Stock", "Total Purchased", "Total Issued", "Current Stock",
                     "Minimum Stock", "Stock Status", "Average Rate", "Stock Value",
                     "Primary Supplier", "Location"],
         "rows": material_rows},
        {"sheet_name": "Purchases", "title": "STOCK IN - PURCHASE REGISTER",
         "columns": ["purchase_code", "date", "supplier", "material", "quantity", "invoice_total", "payment_status"],
         "headers": ["Purchase ID", "Date", "Supplier", "Material", "Quantity", "Invoice Total", "Payment Status"],
         "rows": purchase_rows},
        {"sheet_name": "Issues", "title": "STOCK OUT - MATERIAL ISSUE REGISTER",
         "columns": ["issue_code", "date", "material", "quantity_issued", "issued_to", "department"],
         "headers": ["Issue ID", "Date", "Material", "Quantity Issued", "Issued To", "Department"],
         "rows": issue_rows},
        {"sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
         "columns": ["supplier_code", "name", "category", "contact_person", "phone", "payment_terms"],
         "headers": ["Supplier ID", "Supplier Name", "Category", "Contact Person", "Phone", "Payment Terms"],
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
