from sqlalchemy.orm import Session
from app.models.payment import Payment
from app.models.order import Order
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

class PaymentService:
    
    @staticmethod
    def get_order_payment_summary(db: Session, order_id: int) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError("Order not found")
        
        payments = db.query(Payment).filter(Payment.order_id == order_id).all()
        
        total_received = sum([float(p.amount) for p in payments]) if payments else 0
        pending_payment = float(order.order_value) - total_received
        
        return {
            "order_id": order.order_id,
            "order_value": Decimal(str(order.order_value)),
            "total_received": Decimal(str(total_received)),
            "pending_payment": Decimal(str(pending_payment)),
            "payment_count": len(payments),
            "payments": payments
        }
    
    @staticmethod
    def get_client_payment_summary(db: Session, client_id: int, days: int = 30) -> Dict[str, Any]:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        payments = db.query(Payment).filter(
            Payment.client_id == client_id,
            Payment.date >= start_date
        ).all()
        
        total_received = sum([float(p.amount) for p in payments]) if payments else 0
        
        return {
            "client_id": client_id,
            "period_days": days,
            "total_received": Decimal(str(total_received)),
            "payment_count": len(payments),
            "payments": payments
        }
    
    @staticmethod
    def get_payments_by_mode(db: Session, payment_mode: str, limit: int = 50, offset: int = 0) -> List[Payment]:
        payments = db.query(Payment).filter(
            Payment.payment_mode == payment_mode
        ).offset(offset).limit(limit).all()
        return payments
    
    @staticmethod
    def get_payments_by_type(db: Session, payment_type: str, limit: int = 50, offset: int = 0) -> List[Payment]:
        payments = db.query(Payment).filter(
            Payment.payment_type == payment_type
        ).offset(offset).limit(limit).all()
        return payments
    
    @staticmethod
    def get_overdue_payments(db: Session, days: int = 30, limit: int = 50, offset: int = 0):
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        unpaid_orders = db.query(Order).filter(
            Order.status != "Completed",
            Order.created_at < cutoff_date
        ).offset(offset).limit(limit).all()
        
        overdue_list = []
        for order in unpaid_orders:
            summary = PaymentService.get_order_payment_summary(db, order.id)
            if float(summary["pending_payment"]) > 0:
                overdue_list.append({
                    "order_id": order.order_id,
                    "pending_amount": summary["pending_payment"],
                    "order_date": order.created_at
                })
        
        return overdue_list
