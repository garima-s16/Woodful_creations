"""Keeps Order.total_received / balance consistent with the Payment
register, and provides the profitability/dashboard aggregations."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.project_expense import ProjectExpense
from app.schemas.payment import PaymentCreate
from app.utils.id_generator import generate_unique_code, generate_short_id

CASH_MODES = {"cash"}  # payment_mode is free-text on the model; compare case-insensitively


class OrderService:

    @staticmethod
    def _generate_cash_reference(db: Session, on_date) -> str:
        """CASH-YYYYMMDD-NNN, unique, sequential per calendar day. The user
        never types this - it identifies a cash transaction that has no
        bank/UPI/cheque trail of its own."""
        day_str = on_date.strftime("%Y%m%d")
        prefix = f"CASH-{day_str}-"
        existing_count = (
            db.query(func.count(Payment.id))
            .filter(Payment.reference_number.like(f"{prefix}%"))
            .scalar()
        ) or 0
        seq = existing_count + 1
        candidate = f"{prefix}{seq:03d}"
        # Guard against a rare race (two cash payments recorded the same
        # instant): keep bumping until the reference is actually free.
        while db.query(Payment.id).filter(Payment.reference_number == candidate).first():
            seq += 1
            candidate = f"{prefix}{seq:03d}"
        return candidate

    @staticmethod
    def record_payment(db: Session, data: PaymentCreate) -> Payment:
        order = db.query(Order).filter(Order.id == data.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        is_cash = (data.payment_mode or "").strip().lower() in CASH_MODES
        if is_cash:
            # Cash transactions get a system-generated reference regardless
            # of what (if anything) the client sent - the user should never
            # have to type this, and it must be unique/derivable from the date.
            reference_number = OrderService._generate_cash_reference(db, data.date)
        else:
            reference_number = data.reference_number

        for _ in range(5):
            receipt_code = generate_unique_code(db, Payment, "receipt_code", "RCPT-")
            payment = Payment(
                receipt_code=receipt_code, business_id=generate_short_id(), date=data.date, order_id=data.order_id,
                payment_type=data.payment_type, payment_mode=data.payment_mode, amount=data.amount,
                reference_number=reference_number, received_by=data.received_by, remarks=data.remarks,
            )
            db.add(payment)
            try:
                db.flush()  # so order.payments includes this new row before recompute
            except IntegrityError:
                db.rollback()
                continue

            order.recompute_totals()
            db.add(order)
            db.commit()
            db.refresh(payment)
            return payment
        raise HTTPException(status_code=500, detail="Unable to generate a unique receipt code, please try again")

    @staticmethod
    def profitability(db: Session, order: Order) -> dict:
        expenses = db.query(ProjectExpense).filter(ProjectExpense.order_id == order.id).all()
        total_expenses = sum((e.amount for e in expenses), Decimal("0"))
        gross_profit = (order.order_value or Decimal("0")) - total_expenses
        margin = float(gross_profit / order.order_value) if order.order_value else 0.0

        return {
            "order_id": order.order_code,
            "business_id": order.business_id or "",
            "client": order.client.name if order.client else None,
            "project_type": order.project_type,
            "order_value": float(order.order_value or 0),
            "total_received": float(order.total_received or 0),
            "pending_payment": float(order.balance or 0),
            "project_expenses": float(total_expenses),
            "estimated_gross_profit": float(gross_profit),
            "gross_margin_percent": round(margin, 6),
            "status": order.project_status,
        }
