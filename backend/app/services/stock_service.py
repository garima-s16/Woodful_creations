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
from app.models.location import Location
from app.models.stock_transaction import StockTransfer, StockAdjustment
from app.models.supplier_material import SupplierMaterial
from app.services.notification_service import NotificationService
from app.schemas.purchase import PurchaseCreate
from app.schemas.issue import IssueCreate
from app.schemas.stock_transaction import StockTransferCreate, StockAdjustmentCreate
from app.utils.id_generator import generate_unique_code, generate_short_id


class StockService:

    @staticmethod
    def _apply_stock_receipt(db: Session, material: Material, quantity: Decimal, rate: Decimal, supplier_id: int = None, material_id_for_link: int = None):
        """The actual stock-increase math, shared by record_purchase
        (when goods are received immediately, the default and existing
        behavior) and mark_purchase_received (when a purchase was
        recorded as Ordered and goods arrive later) - one implementation,
        so the weighted-average-rate calculation can't drift between the
        two call sites."""
        material.total_purchased = (material.total_purchased or 0) + quantity
        material.current_stock = (material.current_stock or 0) + quantity
        prior_value = Decimal(str(material.average_rate or 0)) * Decimal(str((material.current_stock or 0) - quantity))
        new_value = prior_value + (quantity * rate)
        if material.current_stock:
            material.average_rate = (new_value / Decimal(str(material.current_stock))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.add(material)

        if supplier_id and material_id_for_link:
            link = db.query(SupplierMaterial).filter(
                SupplierMaterial.supplier_id == supplier_id, SupplierMaterial.material_id == material_id_for_link
            ).first()
            if link:
                link.last_purchase_price = rate
                db.add(link)

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
            purchase_code=purchase_code, business_id=generate_short_id(), date=data.date, supplier_id=data.supplier_id,
            material_id=data.material_id, quantity=data.quantity, unit=data.unit, rate=data.rate,
            taxable_value=taxable_value, gst_percent=data.gst_percent, gst_amount=gst_amount,
            invoice_total=invoice_total, payment_status=data.payment_status,
            receipt_status=data.receipt_status,
        )
        db.add(purchase)

        # "Ordered" means the supplier has been asked for stock that
        # hasn't arrived yet - the material must stay completely
        # untouched until it's explicitly marked received (see
        # mark_purchase_received). "Received" (the default, and the
        # only option that previously existed) increases stock now,
        # exactly as before - existing callers that don't set
        # receipt_status keep their current behavior unchanged.
        if data.receipt_status != "Ordered":
            StockService._apply_stock_receipt(db, material, data.quantity, data.rate, data.supplier_id, data.material_id)
        db.commit()
        db.refresh(purchase)
        if data.receipt_status != "Ordered":
            NotificationService.notify_purchase_received(db, purchase)
        return purchase

    @staticmethod
    def record_issue(db: Session, data: IssueCreate) -> Issue:
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        issue_code = generate_unique_code(db, Issue, "issue_code", "ISS-")

        if data.quantity_issued > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot issue {data.quantity_issued} {data.unit} - only {material.current_stock} in stock",
            )

        issue = Issue(
            issue_code=issue_code, date=data.date, order_id=data.order_id,
            material_id=data.material_id, quantity_issued=data.quantity_issued, unit=data.unit,
            issued_to=data.issued_to, department=data.department, purpose=data.purpose,
            approved_by=data.approved_by, remarks=data.remarks,
        )
        db.add(issue)

        material.total_issued = (material.total_issued or 0) + data.quantity_issued
        material.current_stock = (material.current_stock or 0) - data.quantity_issued
        db.add(material)

        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def record_transfer(db: Session, data: StockTransferCreate) -> StockTransfer:
        """Logs a location move and updates Material's single
        location_id/location fields - not a second stock-by-location
        number (see the model's own docstring for why)."""
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        to_location = db.query(Location).filter(Location.id == data.to_location_id).first()
        if not to_location:
            raise HTTPException(status_code=404, detail="Destination location not found")
        if data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Transfer quantity must be positive")
        if data.quantity > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transfer {data.quantity} {material.unit} - only {material.current_stock} in stock.",
            )

        from_location_id = data.from_location_id or material.location_id

        transfer = StockTransfer(
            material_id=data.material_id, quantity=data.quantity, from_location_id=from_location_id,
            to_location_id=data.to_location_id, transferred_by=data.transferred_by, remarks=data.remarks,
            business_id=generate_short_id(),
        )
        db.add(transfer)

        material.location_id = data.to_location_id
        material.location = to_location.full_path
        db.add(material)

        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def record_adjustment(db: Session, data: StockAdjustmentCreate) -> StockAdjustment:
        """Every change to current_stock outside a purchase/issue must
        go through here - never a silent direct edit. Records the exact
        before/after so the adjustment is fully auditable, and rejects
        anything that would push stock negative."""
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        if data.quantity_delta == 0:
            raise HTTPException(status_code=400, detail="Adjustment quantity cannot be zero")

        stock_before = material.current_stock or 0
        stock_after = stock_before + data.quantity_delta
        if stock_after < 0:
            raise HTTPException(
                status_code=400,
                detail=f"This adjustment would take stock negative ({stock_before} {data.quantity_delta:+} = {stock_after}).",
            )

        adjustment = StockAdjustment(
            material_id=data.material_id, adjustment_type=data.adjustment_type,
            quantity_delta=data.quantity_delta, stock_before=stock_before, stock_after=stock_after,
            reason=data.reason, adjusted_by=data.adjusted_by, business_id=generate_short_id(),
        )
        db.add(adjustment)

        material.current_stock = stock_after
        db.add(material)

        db.commit()
        db.refresh(adjustment)
        return adjustment

    @staticmethod
    def mark_purchase_received(db: Session, purchase_id: int) -> Purchase:
        """Transitions a purchase from Ordered to Received - the point
        stock actually increases for a purchase that was recorded
        ahead of the goods arriving. Rejects anything already
        Received (no double-counting stock from clicking twice)."""
        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        if purchase.receipt_status == "Received":
            raise HTTPException(status_code=400, detail="This purchase has already been received.")

        material = db.query(Material).filter(Material.id == purchase.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        StockService._apply_stock_receipt(db, material, purchase.quantity, purchase.rate, purchase.supplier_id, purchase.material_id)
        purchase.receipt_status = "Received"
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        NotificationService.notify_purchase_received(db, purchase)
        return purchase
