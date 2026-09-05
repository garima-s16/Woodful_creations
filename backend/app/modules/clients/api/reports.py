"""Client-domain report exports: client export and client profile
PDF. Split out of the former monolithic reports.py - see
modules/inventory/api/reports.py's docstring for why."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.clients.models import Client
from app.shared.exporters import build_workbook, xlsx_response
from app.modules.clients.pdf_generator import generate_client_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


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
    return xlsx_response(buffer, filename)


@router.get("/clients/{client_id}/profile.pdf")
def export_client_pdf(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Client profile PDF - available to any authenticated role (client
    contact info isn't the financial data that's restricted elsewhere),
    but the sales-summary/order-value figures inside are genuinely
    gated by role, matching the same protection the normal JSON client
    API already applies for non-master users."""
    from app.modules.clients.models import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    is_privileged = auth.get("role", "user") in ("master",)
    buffer = generate_client_pdf(client, is_privileged)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="client-{client.client_code}.pdf"', "Cache-Control": "no-store, private"},
    )
