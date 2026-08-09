from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.db import SessionLocal
from ..models import Material, Purchase, Issue, Supplier
import io
import pandas as pd
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/reports", tags=["reports"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/stock-dashboard.xlsx", summary="Download stock dashboard workbook")
def export_stock_dashboard(db: Session = Depends(get_db)):
    materials = db.query(Material).all()
    purchases = db.query(Purchase).all()
    issues = db.query(Issue).all()
    suppliers = db.query(Supplier).all()

    df_materials = pd.DataFrame([{
        "Material ID": m.material_id,
        "Material Name": m.name,
        "Category": m.category,
        "Unit": m.unit,
        "Opening Stock": m.opening_stock,
        "Current Stock": m.current_stock,
        "Minimum Stock": m.minimum_stock,
        "Unit Cost": m.unit_cost
    } for m in materials])

    df_purchases = pd.DataFrame([{
        "Purchase No": p.purchase_no,
        "Date": p.date,
        "Supplier": p.supplier.name if p.supplier else None,
        "Material ID": p.material.material_id if p.material else None,
        "Material Name": p.material.name if p.material else None,
        "Quantity": p.quantity,
        "Unit": p.unit,
        "Rate": p.rate,
        "Taxable Value": p.taxable_value,
        "GST%": p.gst_percent,
        "GST Amount": p.gst_amount,
        "Invoice Total": p.invoice_total,
        "Payment Status": p.payment_status
    } for p in purchases])

    df_issues = pd.DataFrame([{
        "Issue No": i.issue_no,
        "Date": i.date,
        "Project": i.project_id,
        "Material ID": i.material.material_id if i.material else None,
        "Material Name": i.material.name if i.material else None,
        "Quantity Issued": i.quantity_issued,
        "Unit": i.unit,
        "Issued To": i.issued_to,
        "Department": i.department,
    } for i in issues])

    df_suppliers = pd.DataFrame([{
        "Supplier ID": s.supplier_id,
        "Name": s.name,
        "Category": s.category,
        "Contact Person": s.contact_person,
        "Phone": s.phone,
        "GSTIN": s.gstin,
        "Payment Terms": s.payment_terms
    } for s in suppliers])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_materials.to_excel(writer, index=False, sheet_name="Material Master")
        df_purchases.to_excel(writer, index=False, sheet_name="Purchases")
        df_issues.to_excel(writer, index=False, sheet_name="Issues")
        df_suppliers.to_excel(writer, index=False, sheet_name="Suppliers")
        writer.save()
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=stock-dashboard.xlsx"}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
