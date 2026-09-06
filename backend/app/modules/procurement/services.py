"""ProcurementService: the purchase business record and supplier
recommendation logic that genuinely belongs to Procurement, not
Inventory (Family 130 P0.2 ownership correction, section 11).

record_purchase/mark_purchase_received create/update the Purchase
record and decide WHEN stock should move - but the actual stock
mutation math (weighted-average rate, ledger entry, location
handling) stays in StockService._apply_stock_receipt
(app.modules.inventory.stock_service), since that is genuinely
Inventory's authority ("Inventory performs physical stock mutation").
This file calls into it rather than duplicating it.

StockService imports back from here (_supplier_options_for_materials,
used to enrich calculate_order_material_requirements/
calculate_at_risk_orders with supplier options) - both sides use a
local, function-level import of the other to avoid a circular
top-level import between the two modules.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase, SupplierMaterial
from app.modules.inventory.schemas import PurchaseCreate
from app.modules.communications.services.notification_service import NotificationService
from app.platform.database.id_generator import generate_unique_code, generate_business_id


class ProcurementService:
    @staticmethod
    def record_purchase(db: Session, data: PurchaseCreate) -> Purchase:
        from app.modules.inventory.stock_service import StockService

        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        purchase_code = generate_unique_code(db, Purchase, "purchase_code", "PUR-")

        taxable_value = (data.quantity * data.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gst_amount = (taxable_value * data.gst_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        invoice_total = taxable_value + gst_amount

        purchase = Purchase(
            purchase_code=purchase_code, business_id=generate_business_id(db), date=data.date,
            expected_delivery_date=data.expected_delivery_date, supplier_id=data.supplier_id,
            material_id=data.material_id, quantity=data.quantity, unit=data.unit, rate=data.rate,
            taxable_value=taxable_value, gst_percent=data.gst_percent, gst_amount=gst_amount,
            invoice_total=invoice_total, payment_status=data.payment_status,
            receipt_status=data.receipt_status, location_id=data.location_id,
            quantity_received=data.quantity if data.receipt_status != "Ordered" else Decimal("0"),
        )
        db.add(purchase)
        db.flush()  # assigns purchase.id without committing, needed as the ledger entry's reference_id below

        # "Ordered" means the supplier has been asked for stock that
        # hasn't arrived yet - the material must stay completely
        # untouched until it's explicitly marked received (see
        # mark_purchase_received). "Received" (the default, and the
        # only option that previously existed) increases stock now,
        # exactly as before - existing callers that don't set
        # receipt_status keep their current behavior unchanged.
        if data.receipt_status != "Ordered":
            StockService._apply_stock_receipt(db, material, data.quantity, data.rate, data.supplier_id, data.material_id, reference_id=purchase.id, location_id=data.location_id)
        db.commit()
        db.refresh(purchase)
        if data.receipt_status != "Ordered":
            NotificationService.notify_purchase_received(db, purchase)
        return purchase

    @staticmethod
    def mark_purchase_received(db: Session, purchase_id: int, quantity_to_receive: Optional[Decimal] = None, location_id: Optional[int] = None) -> Purchase:
        """Transitions a purchase toward Received - the point stock
        actually increases. Supports genuine partial receipts:
        quantity_to_receive defaults to everything still outstanding
        (the original all-or-nothing behavior, unchanged for existing
        callers), but a smaller amount can be passed to receive only
        part of the order. Stock is applied only for the incremental
        amount each call - never the full purchase.quantity again -
        so receiving in two steps can never double-count. Rejects
        anything already fully Received, and rejects receiving more
        than genuinely remains outstanding (the quantity-integrity
        check this feature exists for)."""
        from app.modules.inventory.stock_service import StockService

        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).with_for_update().first()
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        if purchase.receipt_status == "Received":
            raise HTTPException(status_code=400, detail="This purchase has already been received.")

        remaining = (purchase.quantity or Decimal("0")) - (purchase.quantity_received or Decimal("0"))
        if quantity_to_receive is None:
            quantity_to_receive = remaining
        if quantity_to_receive <= 0:
            raise HTTPException(status_code=400, detail="Quantity to receive must be positive.")
        if quantity_to_receive > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot receive {quantity_to_receive} {purchase.unit} - only {remaining} {purchase.unit} remains outstanding on this purchase.",
            )

        material = db.query(Material).filter(Material.id == purchase.material_id).with_for_update().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        receive_location_id = location_id or purchase.location_id
        StockService._apply_stock_receipt(db, material, quantity_to_receive, purchase.rate, purchase.supplier_id, purchase.material_id, reference_id=purchase.id, location_id=receive_location_id)
        purchase.quantity_received = (purchase.quantity_received or Decimal("0")) + quantity_to_receive
        purchase.receipt_status = "Received" if purchase.quantity_received >= purchase.quantity else "Partially Received"
        if receive_location_id and not purchase.location_id:
            purchase.location_id = receive_location_id
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        NotificationService.notify_purchase_received(db, purchase)
        return purchase

    @staticmethod
    def _supplier_options_for_materials(db: Session, material_ids: list, limit_per_material: int = 3) -> dict:
        """Supplier price/lead-time/preference options for a set of
        materials with a genuine shortage (Family 130 section 8: consider
        supplier, lead time, recent price and availability when making a
        recommendation - show which supplier options exist). One bulk
        query regardless of how many materials are passed in, not a
        query per material. Returns {material_id: [option, ...]},
        cheapest/preferred first; a material with no supplier options at
        all is simply absent from the dict."""
        if not material_ids:
            return {}
        rows = (
            db.query(SupplierMaterial)
            .options(selectinload(SupplierMaterial.supplier))
            .filter(SupplierMaterial.material_id.in_(material_ids))
            .all()
        )
        by_material: dict = {}
        for row in rows:
            by_material.setdefault(row.material_id, []).append(row)

        options_by_material = {}
        for material_id, options in by_material.items():
            options.sort(key=lambda r: (
                not r.is_preferred,
                float(r.supplier_price) if r.supplier_price is not None else float("inf"),
            ))
            options_by_material[material_id] = [
                {
                    "supplier_id": r.supplier_id, "supplier_name": r.supplier.name if r.supplier else None,
                    "price": float(r.supplier_price) if r.supplier_price is not None else None,
                    "lead_time_days": r.lead_time_days, "moq": r.moq, "is_preferred": r.is_preferred,
                }
                for r in options[:limit_per_material]
            ]
        return options_by_material
