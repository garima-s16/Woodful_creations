from sqlalchemy.orm import Session
from app.models.order import Order, OrderExpense
from app.models.payment import Payment
from app.models.issue import MaterialIssue
from app.models.purchase import PurchaseOrder
from app.models.material import Material
from typing import Dict, Any
from decimal import Decimal

class OrderService:
    
    @staticmethod
    def get_order_profitability(db: Session, order_id: int) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError(f"Order not found")
        
        total_received = db.query(Payment).filter(
            Payment.order_id == order_id
        ).with_entities(Payment.amount).all()
        total_received_amount = sum([float(p[0]) for p in total_received]) if total_received else 0
        
        total_expenses = db.query(OrderExpense).filter(
            OrderExpense.order_id == order_id
        ).with_entities(OrderExpense.amount).all()
        total_expenses_amount = sum([float(e[0]) for e in total_expenses]) if total_expenses else 0
        
        material_issues = db.query(MaterialIssue).filter(
            MaterialIssue.project_id == order_id
        ).all()
        
        material_cost = 0
        for issue in material_issues:
            last_purchase = db.query(PurchaseOrder).filter(
                PurchaseOrder.material_id == issue.material_id
            ).order_by(PurchaseOrder.date.desc()).first()
            
            if last_purchase:
                unit_cost = float(last_purchase.rate)
                material_cost += unit_cost * issue.quantity_issued
        
        total_expenses_amount += material_cost
        
        order_value = float(order.order_value)
        pending_payment = order_value - total_received_amount
        gross_profit = order_value - total_expenses_amount
        margin_percent = (gross_profit / order_value * 100) if order_value > 0 else 0
        
        return {
            "order_id": order.order_id,
            "order_value": Decimal(str(order_value)),
            "total_received": Decimal(str(total_received_amount)),
            "pending_payment": Decimal(str(pending_payment)),
            "total_expenses": Decimal(str(total_expenses_amount)),
            "gross_profit": Decimal(str(gross_profit)),
            "margin_percent": round(margin_percent, 2),
            "status": order.status
        }
    
    @staticmethod
    def update_order_status(db: Session, order_id: int, new_status: str) -> Order:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.status = new_status
            db.add(order)
            db.commit()
            db.refresh(order)
        return order
    
    @staticmethod
    def get_orders_by_status(db: Session, status: str, limit: int = 50, offset: int = 0):
        orders = db.query(Order).filter(
            Order.status == status
        ).offset(offset).limit(limit).all()
        return orders
    
    @staticmethod
    def get_active_orders(db: Session, limit: int = 50, offset: int = 0):
        active_statuses = ["Enquiry", "Designing", "Approved", "Material Purchase", "Cutting", "Assembly", "Painting", "Ready for Dispatch", "Installation"]
        orders = db.query(Order).filter(
            Order.status.in_(active_statuses)
        ).offset(offset).limit(limit).all()
        return orders
