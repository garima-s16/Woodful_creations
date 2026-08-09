from sqlalchemy.orm import Session
from app.models.purchase import PurchaseOrder
from app.models.material import Material
from app.models.supplier import Supplier
from typing import Dict, Any
from decimal import Decimal

class PurchaseService:
    
    @staticmethod
    def calculate_purchase_totals(rate: Decimal, quantity: int, gst_percent: Decimal = Decimal("18.00")) -> Dict[str, Decimal]:
        rate_decimal = Decimal(str(rate))
        quantity_decimal = Decimal(str(quantity))
        gst_percent_decimal = Decimal(str(gst_percent))
        
        taxable_value = rate_decimal * quantity_decimal
        gst_amount = taxable_value * (gst_percent_decimal / 100)
        invoice_total = taxable_value + gst_amount
        
        return {
            "taxable_value": taxable_value,
            "gst_amount": gst_amount,
            "invoice_total": invoice_total
        }
    
    @staticmethod
    def create_purchase_with_calculations(db: Session, purchase_data: Dict[str, Any]) -> PurchaseOrder:
        totals = PurchaseService.calculate_purchase_totals(
            rate=purchase_data.get("rate"),
            quantity=purchase_data.get("quantity"),
            gst_percent=purchase_data.get("gst_percent", Decimal("18.00"))
        )
        
        purchase = PurchaseOrder(
            purchase_id=purchase_data.get("purchase_id"),
            date=purchase_data.get("date"),
            supplier_id=purchase_data.get("supplier_id"),
            material_id=purchase_data.get("material_id"),
            quantity=purchase_data.get("quantity"),
            unit=purchase_data.get("unit"),
            rate=purchase_data.get("rate"),
            taxable_value=totals["taxable_value"],
            gst_percent=purchase_data.get("gst_percent", Decimal("18.00")),
            gst_amount=totals["gst_amount"],
            invoice_total=totals["invoice_total"],
            payment_status=purchase_data.get("payment_status", "Unpaid"),
            remarks=purchase_data.get("remarks")
        )
        
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        
        return purchase
    
    @staticmethod
    def get_supplier_purchases(db: Session, supplier_id: int, limit: int = 50, offset: int = 0):
        purchases = db.query(PurchaseOrder).filter(
            PurchaseOrder.supplier_id == supplier_id
        ).offset(offset).limit(limit).all()
        return purchases
    
    @staticmethod
    def get_unpaid_purchases(db: Session, limit: int = 50, offset: int = 0):
        purchases = db.query(PurchaseOrder).filter(
            PurchaseOrder.payment_status == "Unpaid"
        ).offset(offset).limit(limit).all()
        return purchases
    
    @staticmethod
    def update_payment_status(db: Session, purchase_id: int, payment_status: str) -> PurchaseOrder:
        purchase = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_id).first()
        if purchase:
            purchase.payment_status = payment_status
            db.add(purchase)
            db.commit()
            db.refresh(purchase)
        return purchase
