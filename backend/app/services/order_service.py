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
from app.models.issue import Issue
from app.models.order_comment import OrderComment
from app.models.daily_task import DailyTask
from app.models.task_comment import TaskComment
from app.models.milestone import Milestone
from app.models.notification import Notification
from app.schemas.payment import PaymentCreate
from app.utils.id_generator import generate_unique_code, generate_business_id

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
                receipt_code=receipt_code, business_id=generate_business_id(db), date=data.date, order_id=data.order_id,
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
        """Actual direct cost = project expenses + the real cost of
        material actually issued to this order (Issue.quantity_issued *
        the material's average_rate at time of query - not a fabricated
        estimate). Previously this only subtracted project expenses,
        which understated cost for any order where material was a
        significant part of the job.

        Labour/production cost is deliberately NOT included: neither
        DailyTask nor ProductionJob tracks hours worked or a wage
        allocation per order, so there is no genuine data to compute it
        from - inventing a formula (e.g. assuming a flat number of
        hours) would be exactly the "invent accounting rules" this
        calculation must not do. If real time-tracking data is added
        later, this is the place to incorporate it."""
        expenses = db.query(ProjectExpense).filter(ProjectExpense.order_id == order.id).all()
        total_expenses = sum((e.amount for e in expenses), Decimal("0"))

        issues = db.query(Issue).filter(Issue.order_id == order.id).all()
        material_cost = sum(
            (Decimal(str(i.quantity_issued or 0)) * Decimal(str(i.material.average_rate or 0)) for i in issues),
            Decimal("0"),
        )

        actual_direct_costs = total_expenses + material_cost
        gross_profit = (order.order_value or Decimal("0")) - actual_direct_costs
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
            "material_cost": float(material_cost),
            "actual_direct_costs": float(actual_direct_costs),
            "estimated_gross_profit": float(gross_profit),
            "gross_margin_percent": round(margin, 6),
            "status": order.project_status,
        }
