"""Keeps Order.total_received / balance consistent with the Payment
register, and provides the profitability/dashboard aggregations."""
from decimal import Decimal
from typing import List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.sales.models import Order, Payment
from app.modules.operations.models import ProjectExpense
from app.modules.operations.models import Issue
from app.modules.inventory.models import Material
from app.modules.sales.schemas import PaymentCreate
from app.platform.database.id_generator import generate_unique_code, generate_business_id

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
        # Locked for the remainder of this transaction so a concurrent
        # payment request against the same order cannot observe the
        # same pre-lock remaining balance and also pass the
        # overpayment check - both would otherwise commit, since
        # neither request's read reflects the other's in-flight write.
        order = db.query(Order).filter(Order.id == data.order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        existing_payments_total = sum((p.amount for p in order.payments), Decimal("0"))
        prospective_total = (order.advance or Decimal("0")) + existing_payments_total + data.amount
        if prospective_total > (order.order_value or Decimal("0")):
            raise HTTPException(
                status_code=400,
                detail=f"This payment of Rs {data.amount} would bring total received to Rs {prospective_total}, "
                       f"which exceeds the order value of Rs {order.order_value}.",
            )

        is_cash = (data.payment_mode or "").strip().lower() in CASH_MODES

        for _ in range(5):
            receipt_code = generate_unique_code(db, Payment, "receipt_code", "RCPT-")
            if is_cash:
                # Cash transactions get a system-generated reference
                # regardless of what (if anything) the client sent - the
                # user should never have to type this, and it must be
                # unique/derivable from the date. Recomputed on every
                # retry attempt (not just once before the loop) so a
                # concurrent request that already claimed the previous
                # candidate doesn't send this one into a permanent
                # collision loop - a database-level partial unique index
                # (see migration 0062) is the actual race guard; this
                # retry is what turns that guard's rejection into a
                # fresh, successful candidate instead of a user-facing error.
                reference_number = OrderService._generate_cash_reference(db, data.date)
            else:
                reference_number = data.reference_number
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
        raise HTTPException(status_code=500, detail="Unable to generate a unique receipt code or cash reference, please try again")

    @staticmethod
    def profitability(db: Session, order: Order) -> dict:
        """A single order's profitability figures - see profitability_bulk
        for the batched version this delegates to, which every caller
        working with more than one order at a time should use instead
        (dashboard/report/analytics call sites all do)."""
        return OrderService.profitability_bulk(db, [order])[order.id]

    @staticmethod
    def profitability_bulk(db: Session, orders: List[Order]) -> dict:
        """Actual direct cost = project expenses + the real cost of
        material actually issued to each order (Issue.quantity_issued *
        the rate frozen on that issue at the time it was recorded -
        never the material's current average_rate, which drifts with
        later purchases and would otherwise silently rewrite the cost
        of an already-completed order).

        Labour/production cost is deliberately NOT included: neither
        DailyTask nor ProductionJob tracks hours worked or a wage
        allocation per order, so there is no genuine data to compute it
        from - inventing a formula (e.g. assuming a flat number of
        hours) would be exactly the "invent accounting rules" this
        calculation must not do. If real time-tracking data is added
        later, this is the place to incorporate it.

        Runs a fixed 2 queries total regardless of how many orders are
        passed in - one for every relevant expense, one for every
        relevant issue, both filtered by order_id IN (...) and grouped
        in Python - rather than the previous per-order query pair that
        made any report/dashboard iterating many orders an N+1 pattern.
        Returns {order.id: figures_dict}."""
        if not orders:
            return {}
        order_ids = [o.id for o in orders]

        expenses_by_order = {}
        for e in db.query(ProjectExpense).filter(ProjectExpense.order_id.in_(order_ids)).all():
            expenses_by_order.setdefault(e.order_id, []).append(e)

        issues_by_order = {}
        for i in (
            db.query(Issue).filter(Issue.order_id.in_(order_ids))
            .options(selectinload(Issue.material)).all()
        ):
            issues_by_order.setdefault(i.order_id, []).append(i)

        results = {}
        for order in orders:
            expenses = expenses_by_order.get(order.id, [])
            total_expenses = sum((e.amount for e in expenses), Decimal("0"))

            issues = issues_by_order.get(order.id, [])
            material_cost = sum(
                (Decimal(str(i.quantity_issued or 0))
                 * Decimal(str(i.rate_at_issue if i.rate_at_issue is not None else (i.material.average_rate or 0)))
                 for i in issues),
                Decimal("0"),
            )

            actual_direct_costs = total_expenses + material_cost
            gross_profit = (order.order_value or Decimal("0")) - actual_direct_costs
            margin = float(gross_profit / order.order_value) if order.order_value else 0.0

            results[order.id] = {
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
                # Contract: this is a RATIO (0.25 == 25%), not a 0-100
                # percent value, despite historically being named
                # "gross_margin_percent" - every consumer multiplies by
                # 100 for display. Named "_ratio" now to make that scale
                # explicit and prevent a 100x misinterpretation error.
                "gross_margin_ratio": round(margin, 6),
                "status": order.project_status,
            }
        return results

    @staticmethod
    def overall_gross_margin(db: Session) -> dict:
        """True aggregate across every order - NOT derived from the
        dashboard's bounded top-orders sample (profitability_bulk on
        just the top 10 would silently understate this once there are
        more than 10 orders, since its profit sum would only cover 10
        orders while total_order_value covers all of them). Same cost
        logic as profitability_bulk (project expenses + material
        actually issued at the rate frozen at issue time, falling back
        to the material's current average_rate only when that wasn't
        recorded), computed as SQL aggregates instead of loaded into
        Python per-order - 3 fixed queries regardless of order count."""
        total_order_value = db.query(func.sum(Order.order_value)).scalar() or Decimal("0")
        total_expenses = db.query(func.sum(ProjectExpense.amount)).scalar() or Decimal("0")
        total_material_cost = (
            db.query(func.sum(Issue.quantity_issued * func.coalesce(Issue.rate_at_issue, Material.average_rate, 0)))
            .join(Material, Issue.material_id == Material.id)
            .filter(Issue.order_id.isnot(None))
            .scalar()
        ) or Decimal("0")

        total_order_value = Decimal(str(total_order_value))
        total_direct_costs = Decimal(str(total_expenses)) + Decimal(str(total_material_cost))
        gross_profit = total_order_value - total_direct_costs
        margin = float(gross_profit / total_order_value) if total_order_value else 0.0

        return {
            "total_order_value": float(total_order_value),
            "total_direct_costs": float(total_direct_costs),
            "estimated_gross_profit": float(gross_profit),
            "gross_margin_ratio": round(margin, 6),
        }
