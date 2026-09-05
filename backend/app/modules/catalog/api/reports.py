"""Catalog-domain report exports: product export and product PDF.
Split out of the former monolithic reports.py - see
modules/inventory/api/reports.py's docstring for why."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.catalog.models import Product
from app.shared.exporters import build_workbook, xlsx_response
from app.modules.catalog.pdf_generator import generate_product_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@router.get("/products.xlsx")
def export_products(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Product Master export. search/category/
    is_active mirror GET /api/products/ exactly, so the export matches
    whatever the person is currently looking at on the Products list."""
    from app.modules.catalog.models import Product

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
    return xlsx_response(buffer, filename)


@router.get("/products/{product_id}/product.pdf")
def export_product_pdf(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    from app.modules.catalog.models import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    buffer = generate_product_pdf(product)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="product-{product.product_code}.pdf"', "Cache-Control": "no-store, private"},
    )
