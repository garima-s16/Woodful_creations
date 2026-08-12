"""Keeps Order.total_received / balance consistent with the Payment
register, and provides the profitability/dashboard aggregations."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import Payment
from app.models.project_expense import ProjectExpense
from app.schemas.payment import PaymentCreate
from app.utils.id_generator import generate_unique_code, generate_short_id


class OrderService:

    @staticmethod
    def record_payment(db: Session, data: PaymentCreate) -> Payment:
        order = db.query(Order).filter(Order.id == data.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        receipt_code = generate_unique_code(db, Payment, "receipt_code", "RCPT-")

        # Receipt ID (business_id) and the payment's own reference number
        # are two different things - the receipt ID identifies the
        # payment record itself; the reference is what the money moved
        # through. For Cash there is no external transaction reference
        # to capture, so the user must not have to invent one - generate
        # a real, unique, dated one instead of leaving it blank or
        # accepting whatever text was typed. Other modes keep whatever
        # real transaction/UPI/cheque reference the user supplied - the
        # system has no way to know that value on its own.
        reference_number = data.reference_number
        if data.payment_mode == "Cash":
            date_str = data.date.strftime("%Y%m%d")
            day_count = db.query(Payment).filter(
                Payment.reference_number.like(f"CASH-{date_str}-%")
            ).count()
            reference_number = None
            for attempt in range(10):
                candidate = f"CASH-{date_str}-{day_count + 1 + attempt:03d}"
                if not db.query(Payment).filter(Payment.reference_number == candidate).first():
                    reference_number = candidate
                    break
            if reference_number is None:
                reference_number = f"CASH-{date_str}-{generate_short_id()[:6]}"

        payment = Payment(
            receipt_code=receipt_code, business_id=generate_short_id(), date=data.date, order_id=data.order_id,
            payment_type=data.payment_type, payment_mode=data.payment_mode, amount=data.amount,
            reference_number=reference_number, received_by=data.received_by, remarks=data.remarks,
        )
        db.add(payment)
        db.flush()  # so order.payments includes this new row before recompute

        order.recompute_totals()
        db.add(order)

        db.commit()
        db.refresh(payment)
        return payment

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
