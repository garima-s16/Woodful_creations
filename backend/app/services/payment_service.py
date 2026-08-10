from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.models.payment import Payment


class PaymentService:

    @staticmethod
    def get_client_payment_summary(db: Session, client_id: int, days: int = 30) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)
        payments = db.query(Payment).filter(
            Payment.client_id == client_id,
            Payment.date >= since,
        ).all()
        total = sum(float(p.amount) for p in payments)
        completed = sum(float(p.amount) for p in payments if p.status == "completed")
        pending = sum(float(p.amount) for p in payments if p.status == "pending")
        return {
            "client_id": client_id,
            "period_days": days,
            "total_amount": total,
            "completed_amount": completed,
            "pending_amount": pending,
            "payment_count": len(payments),
        }

    @staticmethod
    def get_payments_by_mode(db: Session, payment_mode: str) -> List[Payment]:
        return db.query(Payment).filter(Payment.payment_mode == payment_mode).all()

    @staticmethod
    def get_payments_by_type(db: Session, payment_type: str) -> List[Payment]:
        return db.query(Payment).filter(Payment.payment_type == payment_type).all()

    @staticmethod
    def get_overdue_payments(db: Session, days: int = 30) -> List[Payment]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return db.query(Payment).filter(
            Payment.status == "pending",
            Payment.date <= cutoff,
        ).all()
