from sqlalchemy.orm import Session
from app.models.order import Order
from app.models.payment import Payment
from app.models.issue import MaterialIssue
from app.models.purchase import PurchaseOrder
from app.models.material import Material
from typing import List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

class ReportService:
    
    @staticmethod
    def get_order_profitability_report(db: Session, start_date: datetime = None, end_date: datetime = None, limit: int = 100, offset: int = 0):
        query = db.query(Order)
        
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        
        orders = query.offset(offset).limit(limit).all()
        profitability_data = []
        
        for order in orders:
            total_received = db.query(Payment).filter(Payment.order_id == order.id).with_entities(Payment.amount).all()
            total_received_amount = sum([float(p[0]) for p in total_received]) if total_received else 0
            
            total_expenses = db.query(OrderExpense).filter(OrderExpense.order_id == order.id).with_entities(OrderExpense.amount).all()
            total_expenses_amount = sum([float(e[0]) for e in total_expenses]) if total_expenses else 0
            
            material_issues = db.query(MaterialIssue).filter(MaterialIssue.project_id == order.id).all()
            material_cost = 0
            for issue in material_issues:
                last_purchase = db.query(PurchaseOrder).filter(
                    PurchaseOrder.material_id == issue.material_id
                ).order_by(PurchaseOrder.date.desc()).first()
                if last_purchase:
                    material_cost += float(last_purchase.rate) * issue.quantity_issued
            
            total_expenses_amount += material_cost
            order_value = float(order.order_value)
            gross_profit = order_value - total_expenses_amount
            margin_percent = (gross_profit / order_value * 100) if order_value > 0 else 0
            
            profitability_data.append({
                "order_id": order.order_id,
                "client_id": order.client_id,
                "project_type": order.project_type,
                "order_value": Decimal(str(order_value)),
                "total_received": Decimal(str(total_received_amount)),
                "pending_payment": Decimal(str(order_value - total_received_amount)),
                "total_expenses": Decimal(str(total_expenses_amount)),
                "gross_profit": Decimal(str(gross_profit)),
                "margin_percent": round(margin_percent, 2),
                "status": order.status
            })
        
        return profitability_data
    
    @staticmethod
    def get_supplier_performance_report(db: Session, limit: int = 50, offset: int = 0):
        from app.models.supplier import Supplier
        suppliers = db.query(Supplier).offset(offset).limit(limit).all()
        
        supplier_data = []
        for supplier in suppliers:
            purchases = db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier.id).all()
            paid_purchases = [p for p in purchases if p.payment_status == "Paid"]
            unpaid_purchases = [p for p in purchases if p.payment_status == "Unpaid"]
            
            total_purchase_value = sum([float(p.invoice_total) for p in purchases]) if purchases else 0
            total_paid = sum([float(p.invoice_total) for p in paid_purchases]) if paid_purchases else 0
            total_unpaid = sum([float(p.invoice_total) for p in unpaid_purchases]) if unpaid_purchases else 0
            
            supplier_data.append({
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.name,
                "category": supplier.category,
                "total_orders": len(purchases),
                "total_purchase_value": Decimal(str(total_purchase_value)),
                "total_paid": Decimal(str(total_paid)),
                "total_unpaid": Decimal(str(total_unpaid)),
                "payment_terms": supplier.payment_terms
            })
        
        return supplier_data
    
    @staticmethod
    def get_stock_summary_report(db: Session):
        from app.models.material import Material
        materials = db.query(Material).filter(Material.is_active == 1).all()
        
        total_stock_value = 0
        low_stock_materials = []
        out_of_stock_materials = []
        by_category = {}
        
        for material in materials:
            material.current_stock = material.calculate_current_stock()
            status = material.get_stock_status()
            
            if status == "LOW_STOCK":
                low_stock_materials.append(material)
            elif status == "OUT_OF_STOCK":
                out_of_stock_materials.append(material)
            
            if material.category not in by_category:
                by_category[material.category] = []
            by_category[material.category].append(material)
        
        return {
            "total_materials": len(materials),
            "low_stock_count": len(low_stock_materials),
            "out_of_stock_count": len(out_of_stock_materials),
            "low_stock_materials": low_stock_materials,
            "out_of_stock_materials": out_of_stock_materials,
            "by_category": by_category
        }
