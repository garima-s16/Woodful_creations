"""Sales-domain report exports: payments, estimates, orders,
order profitability, and the estimate/order/invoice PDFs. Split out of
the former monolithic reports.py - see modules/inventory/api/reports.py's
docstring for why."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.sales.models import Order, Estimate, Payment
from app.modules.clients.models import Client
from app.modules.sales.order_service import OrderService
from app.shared.exporters import build_workbook, xlsx_response
from app.modules.sales.pdf_generator import generate_order_estimate_pdf, generate_estimate_pdf, generate_invoice_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


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
    return xlsx_response(buffer, filename)


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
    return xlsx_response(buffer, filename)


@router.get("/order-profitability.xlsx")
def export_order_profitability(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    profitability_by_order = OrderService.profitability_bulk(db, orders)
    rows = []
    for o in orders:
        p = profitability_by_order[o.id]
        rows.append({
            "order_id": p["order_id"], "business_id": p["business_id"], "client": p["client"], "project_type": p["project_type"],
            "order_value": p["order_value"], "total_received": p["total_received"],
            "pending_payment": p["pending_payment"], "project_expenses": p["project_expenses"],
            "material_cost": p["material_cost"],
            "estimated_gross_profit": p["estimated_gross_profit"],
            "gross_margin_ratio": p["gross_margin_ratio"], "status": p["status"],
        })
    columns = ["order_id", "business_id", "client", "project_type", "order_value", "total_received",
               "pending_payment", "project_expenses", "material_cost", "estimated_gross_profit",
               "gross_margin_ratio", "status"]
    headers = ["Order ID", "Business ID", "Client", "Project Type", "Order Value", "Total Received",
               "Pending Payment", "Project Expenses", "Material Cost", "Estimated Gross Profit",
               "Gross Margin %", "Status"]
    buffer = build_workbook([{"sheet_name": "Order Profitability", "title": "ORDER-WISE PROFITABILITY REPORT",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["order_value", "total_received", "pending_payment",
                                                  "project_expenses", "material_cost", "estimated_gross_profit"]}])
    return xlsx_response(buffer, "order-profitability.xlsx")


@router.get("/orders.xlsx")
def export_orders(
    status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Sales/Orders Register export. Mirrors GET /api/orders/'s
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
    risk_flags = OrderService.bulk_attention_flags(db, [o.id for o in orders]) if orders else {}
    rows = []
    for o in orders:
        flag = risk_flags.get(o.id, {})
        row = {
            "order_id": o.business_id or "", "order_code": o.order_code,
            "client": o.client.name if o.client else "", "project_type": o.project_type or "",
            "order_date": o.order_date.strftime("%d-%m-%Y") if o.order_date else "",
            "delivery_date": o.delivery_date.strftime("%d-%m-%Y") if o.delivery_date else "",
            "status": o.project_status, "progress_percent": o.progress_percent,
            "risk_level": flag.get("risk_level", ""), "risk_reason": flag.get("reason") or "",
        }
        if is_privileged:
            row["order_value"] = float(o.order_value or 0)
            row["total_received"] = float(o.total_received or 0)
            row["balance"] = float(o.balance or 0)
        rows.append(row)

    columns = ["order_id", "order_code", "client", "project_type", "order_date", "delivery_date",
               "status", "progress_percent", "risk_level", "risk_reason"]
    headers = ["Order ID", "Order Code", "Client", "Project Type", "Order Date", "Delivery Date",
               "Status", "Progress %", "Delivery Risk", "Risk Reason"]
    total_columns = []
    if is_privileged:
        columns[6:6] = ["order_value", "total_received", "balance"]
        headers[6:6] = ["Order Value", "Total Received", "Balance"]
        total_columns = ["order_value", "total_received", "balance"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Orders", str(len(orders)))]
    critical_count = sum(1 for f in risk_flags.values() if f.get("risk_level") == "CRITICAL")
    at_risk_count = sum(1 for f in risk_flags.values() if f.get("risk_level") == "AT_RISK")
    if critical_count or at_risk_count:
        summary.append(("Critical / At Risk", f"{critical_count} / {at_risk_count}"))
    if is_privileged:
        summary.append(("Total Order Value", f"Rs {sum(r['order_value'] for r in rows):,.2f}"))
        summary.append(("Total Outstanding", f"Rs {sum(r['balance'] for r in rows):,.2f}"))

    buffer = build_workbook([{
        "sheet_name": "Orders", "title": "SALES / ORDERS REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": total_columns, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"orders_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/orders/{order_id}/estimate.pdf")
def export_order_estimate_pdf(order_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """This PDF includes order_value/total_received -
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


@router.get("/estimates/{estimate_id}/quote.pdf")
def export_estimate_quote_pdf(estimate_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """This PDF includes per-line-item rate/amount -
    the same line-item pricing test_financial_rbac.py already
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
