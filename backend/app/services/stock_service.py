"""Keeps Material.current_stock / total_purchased / total_issued consistent
with the Purchase and Issue registers. All writes go through here rather
than routes touching Material directly, so stock can never drift from its
transaction history."""
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.schemas.purchase import PurchaseCreate
from app.schemas.issue import IssueCreate
from app.utils.id_generator import generate_unique_code


class StockService:

    @staticmethod
    def record_purchase(db: Session, data: PurchaseCreate) -> Purchase:
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        purchase_code = generate_unique_code(db, Purchase, "purchase_code", "PUR-")

        taxable_value = (data.quantity * data.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gst_amount = (taxable_value * data.gst_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        invoice_total = taxable_value + gst_amount

        purchase = Purchase(
            purchase_code=purchase_code, date=data.date, supplier_id=data.supplier_id,
            material_id=data.material_id, quantity=data.quantity, unit=data.unit, rate=data.rate,
            taxable_value=taxable_value, gst_percent=data.gst_percent, gst_amount=gst_amount,
            invoice_total=invoice_total, payment_status=data.payment_status,
        )
        db.add(purchase)

        qty_int = int(data.quantity)
        material.total_purchased = (material.total_purchased or 0) + qty_int
        material.current_stock = (material.current_stock or 0) + qty_int
        # Weighted average rate across existing stock + this purchase.
        prior_value = Decimal(str(material.average_rate or 0)) * Decimal(str((material.current_stock or 0) - qty_int))
        new_value = prior_value + (data.quantity * data.rate)
        if material.current_stock:
            material.average_rate = (new_value / Decimal(str(material.current_stock))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.add(material)

        db.commit()
        db.refresh(purchase)
        return purchase

    @staticmethod
    def record_issue(db: Session, data: IssueCreate) -> Issue:
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        issue_code = generate_unique_code(db, Issue, "issue_code", "ISS-")

        qty_int = int(data.quantity_issued)
        if qty_int > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot issue {qty_int} {data.unit} - only {material.current_stock} in stock",
            )

        issue = Issue(
            issue_code=issue_code, date=data.date, order_id=data.order_id,
            material_id=data.material_id, quantity_issued=data.quantity_issued, unit=data.unit,
            issued_to=data.issued_to, department=data.department, purpose=data.purpose,
            approved_by=data.approved_by, remarks=data.remarks,
        )
        db.add(issue)

        material.total_issued = (material.total_issued or 0) + qty_int
        material.current_stock = (material.current_stock or 0) - qty_int
        db.add(material)

        db.commit()
        db.refresh(issue)
        return issue
