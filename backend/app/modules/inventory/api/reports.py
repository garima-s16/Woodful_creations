"""Inventory-domain report exports: purchases, material issues,
suppliers, materials, and the combined stock dashboard. Split out of
the former monolithic reports.py, which mixed every domain's exports
(inventory, sales, HR, operations, clients, catalog) into one 1350-line
file grouped by "this is a report" rather than by actual product
domain."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.inventory.models import Purchase, Material, Supplier
from app.modules.operations.models import Issue
from app.shared.exporters import build_workbook, xlsx_response

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


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
    return xlsx_response(buffer, "purchases.xlsx")


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
    return xlsx_response(buffer, "issues.xlsx")


@router.get("/suppliers.xlsx")
def export_suppliers(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Supplier Master export, matching export_products'/export_materials'
    established pattern. No privileged-gating - Supplier itself carries
    no financial field (per-material pricing lives on the separate
    SupplierMaterial table, not exported here)."""
    from app.modules.inventory.models import Supplier

    query = db.query(Supplier)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Supplier.name.ilike(like), Supplier.supplier_code.ilike(like),
                                  Supplier.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Supplier.category == category)
        filters_applied.append(f"Category: {category}")

    suppliers = query.order_by(Supplier.name).all()
    rows = [{
        "supplier_id": s.business_id or "", "supplier_code": s.supplier_code, "name": s.name,
        "category": s.category or "", "contact_person": s.contact_person or "", "phone": s.phone or "",
        "gstin": s.gstin or "", "payment_terms": s.payment_terms or "",
    } for s in suppliers]

    columns = ["supplier_id", "supplier_code", "name", "category", "contact_person", "phone",
               "gstin", "payment_terms"]
    headers = ["Supplier ID", "Supplier Code", "Supplier Name", "Category", "Contact Person", "Phone",
               "GSTIN", "Payment Terms"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Suppliers", str(len(suppliers)))],
    }])
    filename = f"supplier_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/materials.xlsx")
def export_materials(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    low_stock_only: bool = Query(False), active_only: bool = Query(False),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Material Master export, matching export_products' established
    pattern. Filters mirror GET /api/materials/'s main params."""
    from app.modules.inventory.models import Material

    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Material)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Material.name.ilike(like), Material.material_code.ilike(like),
                                  Material.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Material.category == category)
        filters_applied.append(f"Category: {category}")
    if low_stock_only:
        query = query.filter(Material.current_stock <= Material.minimum_stock)
        filters_applied.append("Low stock only")
    if active_only:
        query = query.filter(Material.is_active == True)  # noqa: E712
        filters_applied.append("Active only")

    materials = query.order_by(Material.name).all()
    rows = []
    for m in materials:
        row = {
            "material_id": m.business_id or "", "material_code": m.material_code, "name": m.name,
            "category": m.category or "", "subcategory": m.subcategory.name if m.subcategory else "",
            "unit": m.unit, "current_stock": float(m.current_stock), "minimum_stock": float(m.minimum_stock),
            "location": m.location_ref.name if m.location_ref else (m.location or ""),
            "supplier": m.primary_supplier.name if m.primary_supplier else "",
            "status": "Active" if m.is_active else "Inactive",
        }
        if is_privileged:
            row["average_rate"] = float(m.average_rate) if m.average_rate is not None else None
        rows.append(row)

    columns = ["material_id", "material_code", "name", "category", "subcategory", "unit",
               "current_stock", "minimum_stock", "location", "supplier", "status"]
    headers = ["Material ID", "Material Code", "Material Name", "Category", "Subcategory", "Unit",
               "Current Stock", "Minimum Stock", "Location", "Supplier", "Status"]
    if is_privileged:
        columns += ["average_rate"]
        headers += ["Average Rate"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Materials", "title": "MATERIAL MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Materials", str(len(materials)))],
    }])
    filename = f"material_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


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
    return xlsx_response(buffer, "stock-dashboard.xlsx")
