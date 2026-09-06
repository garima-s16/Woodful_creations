"""Keeps Order.total_received / balance consistent with the Payment
register, and provides the profitability/dashboard aggregations, plus
the deterministic Order Health/Risk contract (Family 130 P0.1) that
both the chatbot and the plain Order Health API consume."""
from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.sales.models import Order, Payment
from app.modules.operations.models import ProjectExpense
from app.modules.operations.models import Issue, ProductionJob, DailyTask
from app.modules.inventory.models import Material
from app.modules.hr.models import Employee
from app.modules.sales.schemas import PaymentCreate
from app.modules.ai.security import sanitize_untrusted_text
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
    def compute_order_health(db: Session, order_id: int, override_delivery_date: Optional[datetime] = None) -> Optional[dict]:
        """Deterministic, explainable Order Health/Risk - the single
        authoritative computation for "is this order okay, and why".
        Reuses only genuinely existing, queryable signals (linked
        tasks, production jobs, materials actually issued, delivery
        date, and StockService.calculate_order_material_requirements -
        the same shortage calculation the dashboard/daily-tasks-list/
        at-risk-orders chatbot query already use for this exact order).
        Never a fabricated figure or an invented score.

        Family 130 P0.50 (Delivery Risk Engine) extends this same
        function rather than creating a second risk engine: a 4-level
        risk_level (ON_TRACK/WATCH/AT_RISK/CRITICAL, deterministic
        rules, not a numeric score), delivery_timing (honest days-
        remaining/overdue wording), evidence (the raw numbers behind
        each reason), business_impact (a plain-language summary built
        only from findings actually present), and production_summary
        (section 14's job breakdown).

        override_delivery_date (section 11 - What-If Scheduling) lets a
        caller ask "what would risk look like if this order's delivery
        date were X" using this exact same calculation - never a
        second, simplified simulation engine - and without writing
        anything to the database; the order's real delivery_date is
        never touched. None (the default) means "use the order's real,
        committed date", so every existing caller is unaffected.

        Pure computation, no side effects (no persistence, no
        role-based redaction, no chat-specific text) - so both the
        chatbot's order-risk workspace (services.py's
        _order_risk_workspace, which additionally persists this as an
        AIWorkspaceReport and adds chat-specific formatting) and the
        plain GET /api/orders/{id}/health REST endpoint call this same
        function rather than each computing risk independently. This
        is also the structured contract a future AI/agent should
        consume instead of re-deriving risk logic of its own (Family
        130 P0.1 section 22-24, P0.50 section 24).

        Returns None if the order doesn't exist - callers decide how
        to surface that (404 for the API, a plain "not found" message
        for chat)."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        effective_delivery_date = override_delivery_date if override_delivery_date is not None else order.delivery_date

        now = datetime.utcnow()
        tasks = db.query(DailyTask).filter(DailyTask.order_id == order_id).all()
        blocked_tasks = [t for t in tasks if t.status == "BLOCKED"]
        open_tasks = [t for t in tasks if t.status != "DONE"]
        # due_date is real, queried data (see DailyTask.due_date - defaults
        # from the order's delivery_date at task creation, or a Master
        # override) - a task that is open and already past it is a genuine
        # finding distinct from "BLOCKED" (an employee may simply not have
        # marked it), so it must not be silently invisible to Health/Risk.
        overdue_tasks = [t for t in open_tasks if t.id not in {b.id for b in blocked_tasks}
                          and t.due_date and t.due_date < now]

        jobs = db.query(ProductionJob).filter(ProductionJob.order_id == order_id).all()
        incomplete_jobs = [j for j in jobs if j.status != "Completed"]
        # blocker_reason is freestanding on ProductionJob (no dedicated
        # "Blocked" status - see the model's own comment), so a job that
        # carries one is a genuine production blocker even though the
        # earlier incomplete_jobs count alone could not distinguish it
        # from ordinary in-progress work.
        production_blockers = [j for j in jobs if (j.blocker_reason or "").strip()]

        # Production connection (P0.50 section 14) - the structured
        # job breakdown the spec's own example asks for, from exactly
        # the same jobs list already queried above.
        production_summary = {
            "has_production_jobs": bool(jobs),
            "total_jobs": len(jobs),
            "completed_jobs": len([j for j in jobs if j.status == "Completed"]),
            "pending_jobs": len(incomplete_jobs),
            "blocked_jobs": len(production_blockers),
        }

        issued_materials = db.query(Issue).filter(Issue.order_id == order_id).all()

        from app.modules.inventory.stock_service import StockService
        material_requirements = StockService.calculate_order_material_requirements(db, order_id)
        material_shortages = [row for row in material_requirements["materials"] if row["shortage"] > 0]

        # Actual completion (spec section 7: distinguish target/promised
        # delivery from actual completion/delivery "where supported by
        # current data" - without adding a redundant date column). The
        # order lifecycle already logs every project_status change to
        # AuditLog (see update_order's log_action call), so the moment
        # project_status genuinely became "Completed" is real, existing
        # data - the first such audit row, not the most recent, since a
        # later unrelated field edit must not look like a re-completion.
        actual_completion_date = None
        if order.project_status == "Completed":
            from app.platform.audit.audit import AuditLog
            status_logs = (
                db.query(AuditLog)
                .filter(AuditLog.module_name == "orders", AuditLog.record_id == order.id)
                .order_by(AuditLog.created_at.asc())
                .all()
            )
            # Filtered in Python rather than a JSON-path DB predicate -
            # this is a single order's own audit trail (bounded, small),
            # and avoids relying on JSON operator support that differs
            # between the Postgres production database and SQLite tests.
            for log in status_logs:
                if isinstance(log.new_value, dict) and log.new_value.get("project_status") == "Completed":
                    actual_completion_date = log.created_at.isoformat()
                    break

        # P0.50 Delivery Timing Intelligence - honest wording for every
        # case (missing date, today, future, overdue), never negative/
        # confusing phrasing. days_remaining is negative when overdue;
        # is_overdue is the explicit, unambiguous signal callers should
        # branch on rather than re-deriving it from the sign of a number.
        delivery_timing = {"has_delivery_date": bool(effective_delivery_date), "days_remaining": None,
                            "is_overdue": False, "urgency_text": "Delivery date not set"}
        days_left = None
        if effective_delivery_date:
            days_left = (effective_delivery_date.date() - now.date()).days
            delivery_timing["days_remaining"] = days_left
            delivery_timing["is_overdue"] = days_left < 0
            if days_left < 0:
                delivery_timing["urgency_text"] = f"{abs(days_left)} day{'s' if abs(days_left) != 1 else ''} overdue"
            elif days_left == 0:
                delivery_timing["urgency_text"] = "Due today"
            elif days_left == 1:
                delivery_timing["urgency_text"] = "1 day remaining"
            else:
                delivery_timing["urgency_text"] = f"{days_left} days remaining"

        delivery_at_risk = days_left is not None and 0 <= days_left <= 3 and (bool(open_tasks) or bool(incomplete_jobs))
        delivery_overdue_open = days_left is not None and days_left < 0 and order.project_status != "Completed"

        has_active_blocker = bool(blocked_tasks or material_shortages or production_blockers)

        # P0.50 section 6 - a small, deterministic 4-level model, not an
        # opaque score. CRITICAL is reserved for genuinely severe cases
        # (delivery commitment already missed and still open, or
        # imminent with a real blocker still active) - AT_RISK covers
        # every case the original 2-level model already caught, so no
        # order that used to be flagged becomes silently invisible.
        if delivery_overdue_open and (has_active_blocker or bool(overdue_tasks)):
            risk_level = "CRITICAL"
        elif days_left is not None and days_left <= 1 and has_active_blocker:
            risk_level = "CRITICAL"
        elif blocked_tasks or overdue_tasks or delivery_at_risk or material_shortages or production_blockers or delivery_overdue_open:
            risk_level = "AT_RISK"
        elif days_left is not None and 4 <= days_left <= 7 and (bool(open_tasks) or bool(incomplete_jobs)):
            risk_level = "WATCH"
        else:
            risk_level = "ON_TRACK"

        # Explainability (spec section 14/21: "if a health status is
        # implemented ... make the reason visible") - one plain-language
        # line per genuine finding, never a bare score.
        reasons = []
        for t in blocked_tasks:
            reasons.append(f"Task '{t.task_description}' is blocked: "
                            f"{sanitize_untrusted_text(t.delay_reason) or 'no reason recorded'}")
        for t in overdue_tasks:
            reasons.append(f"Task '{t.task_description}' is overdue "
                            f"(was due {t.due_date.date().isoformat()}).")
        for row in material_shortages:
            reasons.append(f"Short {float(row['shortage']):g} {row['unit']} of {row['material_name']}")
        for j in production_blockers:
            reasons.append(f"Production job '{j.job_code}' is blocked: "
                            f"{sanitize_untrusted_text(j.blocker_reason)}")
        if delivery_overdue_open:
            reasons.append(f"Delivery commitment already missed - {delivery_timing['urgency_text']} and the order is not yet completed.")
        elif delivery_at_risk:
            reasons.append(f"Delivery date is close ({delivery_timing['urgency_text']}) with work still open.")
        elif risk_level == "WATCH":
            reasons.append(f"Delivery is approaching ({delivery_timing['urgency_text']}) with work still open - worth monitoring.")
        if not reasons:
            # Section 3: never claim "no risk" when a signal was not
            # actually checkable - this line only fires once every signal
            # above (tasks, jobs, materials, delivery) was actually queried
            # and came back clean, so it is a genuine finding, not a default.
            reasons.append("No blocker found from available data - work is progressing normally.")

        # Next Action (spec section 5): one authoritative, priority-ordered
        # pointer to what actually needs attention next, so a generic open
        # task never hides a stronger business blocker. Computed here, once,
        # from the same signals above - the REST API, chatbot workspace, and
        # Order Detail UI all read this field rather than each re-deriving
        # "what's next" from raw tasks independently.
        next_action = None
        if delivery_overdue_open:
            next_action = {"type": "delivery_overdue", "description": "Review this order's missed delivery commitment",
                           "detail": delivery_timing["urgency_text"]}
        elif blocked_tasks:
            t = blocked_tasks[0]
            next_action = {"type": "blocked_task", "description": f"Unblock '{t.task_description}'",
                           "detail": sanitize_untrusted_text(t.delay_reason) or "No reason recorded"}
        elif material_shortages:
            row = material_shortages[0]
            next_action = {"type": "material_shortage",
                           "description": f"Resolve shortage of {row['material_name']}",
                           "detail": f"Short {float(row['shortage']):g} {row['unit']}"}
        elif production_blockers:
            j = production_blockers[0]
            next_action = {"type": "production_blocker", "description": f"Resolve blocker on job '{j.job_code}'",
                           "detail": sanitize_untrusted_text(j.blocker_reason)}
        elif overdue_tasks:
            t = overdue_tasks[0]
            next_action = {"type": "overdue_task", "description": f"Follow up on overdue task '{t.task_description}'",
                           "detail": f"Was due {t.due_date.date().isoformat()}"}
        elif delivery_at_risk:
            next_action = {"type": "delivery_risk", "description": "Delivery date is close with work still open",
                           "detail": delivery_timing["urgency_text"]}
        elif open_tasks:
            t = sorted(open_tasks, key=lambda x: x.date)[0]
            next_action = {"type": "open_task", "description": t.task_description, "detail": None}
        # else: no genuine next action exists - never fabricate one.

        # Readiness (spec section 6): structured, per-dimension state built
        # only from signals that already exist - never a synthetic percent.
        # "unavailable" means the dimension has no real data to evaluate yet,
        # not that it passed. Payment/commercial amounts stay out of this
        # (financial figures remain MASTER-only, gated by the API caller);
        # this only reports structural completeness anyone may see.
        readiness = {
            "commercial": (
                "ready" if getattr(order, "items", None) else "unavailable"
            ),
            "material": (
                "blocked" if material_shortages else
                ("ready" if material_requirements["materials"] else "unavailable")
            ),
            "production": (
                "blocked" if production_blockers else
                "ready" if (jobs and not incomplete_jobs) else
                "in_progress" if jobs else "unavailable"
            ),
            "delivery": (
                "delivered" if actual_completion_date else
                "overdue" if delivery_overdue_open else
                "at_risk" if delivery_at_risk else
                "on_track" if effective_delivery_date else "unavailable"
            ),
        }

        # Evidence (spec section 9): the raw numbers behind each reason
        # above, for a caller that wants structured data rather than a
        # sentence - built from exactly the same signals, never a
        # second, independently-derived figure.
        evidence = []
        for t in blocked_tasks:
            evidence.append({"type": "blocked_task", "task": t.task_description,
                              "reason": sanitize_untrusted_text(t.delay_reason) or "No reason recorded"})
        for t in overdue_tasks:
            evidence.append({"type": "overdue_task", "task": t.task_description,
                              "due_date": t.due_date.date().isoformat(),
                              "days_overdue": (now.date() - t.due_date.date()).days})
        blocked_job_material_ids = {j.material_id for j in production_blockers if j.material_id}
        for row in material_shortages:
            procurement_status = (
                "purchase_covers_gap" if row["pending_purchase_quantity"] > 0 and row["gap_before_pending_supply"] <= 0
                else "purchase_placed_insufficient" if row["pending_purchase_quantity"] > 0
                else "no_purchase_placed"
            )
            evidence.append({
                "type": "material_shortage", "material": row["material_name"],
                "required": float(row["required"]), "available": float(row["available"]),
                "shortage": float(row["shortage"]), "unit": row["unit"],
                "procurement_status": procurement_status,
                "pending_purchase_quantity": float(row["pending_purchase_quantity"]),
                "blocks_production": row["material_id"] in blocked_job_material_ids,
                "supplier_options": row["supplier_options"],
            })
        for j in production_blockers:
            evidence.append({"type": "production_blocker", "job_code": j.job_code,
                              "reason": sanitize_untrusted_text(j.blocker_reason)})
        if effective_delivery_date:
            evidence.append({"type": "delivery_timing", "days_remaining": delivery_timing["days_remaining"],
                              "is_overdue": delivery_timing["is_overdue"]})

        # Business impact (spec section 17): a plain-language summary of
        # what the findings above actually mean, built only from what
        # was genuinely found - never a generic line when risk_level
        # happens to be non-ON_TRACK for a reason this order doesn't have.
        impact_parts = []
        if delivery_overdue_open:
            impact_parts.append("the delivery commitment has already been missed")
        elif delivery_at_risk or risk_level == "WATCH":
            impact_parts.append("the delivery commitment is at risk")
        if material_shortages:
            no_purchase_yet = any(row["pending_purchase_quantity"] <= 0 for row in material_shortages)
            if no_purchase_yet:
                impact_parts.append("production cannot fully proceed until the material shortage is resolved and no purchase has been placed yet")
            else:
                impact_parts.append("production cannot fully proceed until the pending purchase is received")
        if production_blockers:
            impact_parts.append("production is directly blocked")
        if blocked_tasks or overdue_tasks:
            impact_parts.append("required work is behind schedule")
        business_impact = (
            "No material business impact identified from available data." if not impact_parts
            else "Because " + "; ".join(impact_parts) + "."
        )

        return {
            "order_id": order.id,
            "order_code": order.order_code,
            "stage": order.project_status,
            "risk_level": risk_level,
            "reasons": reasons,
            "evidence": evidence,
            "business_impact": business_impact,
            "delivery_timing": delivery_timing,
            "production_summary": production_summary,
            "next_action": next_action,
            "readiness": readiness,
            "blocked_tasks": [
                {"id": t.id, "description": t.task_description,
                 "reason": sanitize_untrusted_text(t.delay_reason) or "No reason recorded"}
                for t in blocked_tasks
            ],
            "overdue_tasks": [
                {"id": t.id, "description": t.task_description, "due_date": t.due_date.isoformat()}
                for t in overdue_tasks
            ],
            "production_blockers": [
                {"id": j.id, "job_code": j.job_code, "reason": sanitize_untrusted_text(j.blocker_reason)}
                for j in production_blockers
            ],
            "open_task_count": len(open_tasks),
            "incomplete_production_jobs": len(incomplete_jobs),
            "materials_issued_count": len(issued_materials),
            "material_shortages": [
                {
                    "material_id": row["material_id"], "material_name": row["material_name"], "unit": row["unit"],
                    "shortage": float(row["shortage"]), "supplier_options": row["supplier_options"],
                }
                for row in material_shortages
            ],
            "delivery_date": effective_delivery_date.isoformat() if effective_delivery_date else None,
            "real_delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "is_simulation": override_delivery_date is not None,
            "actual_completion_date": actual_completion_date,
            "delivery_at_risk": delivery_at_risk,
        }

    @staticmethod
    def bulk_attention_flags(db: Session, order_ids: List[int]) -> dict:
        """Lightweight, batched "does this order need attention" flag for
        the Order List (Family 130 P0.1 s.11) - fixed-count queries
        regardless of how many orders are passed in, so listing a page of
        orders never becomes an N+1 or re-runs compute_order_health's
        per-order material-shortage calculation for every row.

        Deliberately narrower than compute_order_health: covers only
        blocked tasks, overdue tasks (real DailyTask.due_date data),
        production blockers, and delivery risk - the signals cheap to
        batch with plain IN-queries. Material-shortage risk is NOT
        included here; that is StockService.calculate_at_risk_orders's
        heavier BOM/stock-reservation calculation, already used
        separately by the business-wide dashboard, and is not
        duplicated on every Order List page load. A caller combining
        this with that dashboard result gets the full picture; this
        function alone is a genuine but partial signal, not the
        complete Health/Risk contract for a single order (GET
        /orders/{id}/health remains authoritative for that).

        Returns {order_id: {"needs_attention": bool, "reason": str|None,
        "risk_level": str}} for every id in order_ids (never a sparse/
        omitted key). risk_level uses the same P0.50 4-level model as
        compute_order_health, built only from the signals already
        gathered above - material-shortage-driven CRITICAL/AT_RISK is
        still only available from the single-order health endpoint."""
        if not order_ids:
            return {}
        now = datetime.utcnow()

        tasks = db.query(DailyTask).filter(DailyTask.order_id.in_(order_ids)).all()
        blocked_by_order: dict = {}
        overdue_by_order: dict = {}
        open_by_order: dict = {}
        for t in tasks:
            if t.status == "DONE":
                continue
            open_by_order[t.order_id] = open_by_order.get(t.order_id, 0) + 1
            if t.status == "BLOCKED":
                blocked_by_order.setdefault(t.order_id, t)
            elif t.due_date and t.due_date < now:
                overdue_by_order.setdefault(t.order_id, t)

        jobs = db.query(ProductionJob).filter(ProductionJob.order_id.in_(order_ids)).all()
        blocker_by_order: dict = {}
        incomplete_job_by_order: dict = {}
        for j in jobs:
            if j.status != "Completed":
                incomplete_job_by_order[j.order_id] = incomplete_job_by_order.get(j.order_id, 0) + 1
            if (j.blocker_reason or "").strip():
                blocker_by_order.setdefault(j.order_id, j)

        orders = db.query(Order.id, Order.delivery_date, Order.project_status).filter(Order.id.in_(order_ids)).all()

        result = {}
        for order_id, delivery_date, project_status in orders:
            reason = None
            has_blocker = order_id in blocked_by_order or order_id in blocker_by_order
            is_overdue_open = False
            if order_id in blocked_by_order:
                reason = f"Task '{blocked_by_order[order_id].task_description}' is blocked"
            elif order_id in blocker_by_order:
                reason = f"Production job '{blocker_by_order[order_id].job_code}' is blocked"
            elif order_id in overdue_by_order:
                reason = f"Task '{overdue_by_order[order_id].task_description}' is overdue"
            days_left = None
            if delivery_date:
                days_left = (delivery_date.date() - now.date()).days
                is_overdue_open = days_left < 0 and project_status != "Completed"
                if reason is None and days_left <= 3 and (order_id in open_by_order or order_id in incomplete_job_by_order):
                    reason = "Delivery date is within 3 days with work still open"
            if is_overdue_open and reason is None:
                reason = "Delivery date has passed and the order is not yet completed"

            # Same P0.50 4-level model as compute_order_health, using
            # only the signals this function already gathered - not a
            # second, independently-derived risk definition.
            if is_overdue_open and (has_blocker or order_id in overdue_by_order):
                risk_level = "CRITICAL"
            elif days_left is not None and days_left <= 1 and has_blocker:
                risk_level = "CRITICAL"
            elif reason is not None or is_overdue_open:
                risk_level = "AT_RISK"
            elif days_left is not None and 4 <= days_left <= 7 and (order_id in open_by_order or order_id in incomplete_job_by_order):
                risk_level = "WATCH"
            else:
                risk_level = "ON_TRACK"

            result[order_id] = {"needs_attention": reason is not None, "reason": reason, "risk_level": risk_level}
        return result

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

        Labour cost (Family P0.45, see labour_cost_bulk) is
        deliberately kept OUT of actual_direct_costs/
        estimated_gross_profit/gross_margin_ratio above - those three
        are an existing, already-tested contract that predates labour
        attribution existing at all. It is instead exposed as separate,
        additive keys (labour_cost, labour_is_attributed, labour_days,
        labour_method, total_direct_cost_with_labour,
        gross_profit_with_labour, gross_margin_ratio_with_labour), so a
        caller who wants labour-inclusive profitability opts into it
        explicitly rather than an existing caller silently getting a
        different number than before.

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
        labour_by_order = OrderService.labour_cost_bulk(db, orders)
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

            # Labour (Family P0.45) is deliberately kept as separate,
            # clearly-labelled additional keys rather than folded into
            # actual_direct_costs/estimated_gross_profit/gross_margin_ratio
            # above - those three are an existing, already-tested
            # contract with callers that predate labour attribution
            # existing at all; silently changing their meaning would be
            # exactly the "break existing APIs" this work must not do.
            labour = labour_by_order.get(order.id, {"attributed_cost": Decimal("0"), "is_attributed": False, "labour_days": 0, "method": ""})
            total_cost_with_labour = actual_direct_costs + labour["attributed_cost"]
            gross_profit_with_labour = (order.order_value or Decimal("0")) - total_cost_with_labour
            margin_with_labour = float(gross_profit_with_labour / order.order_value) if order.order_value else 0.0

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
                # Family P0.45 additions - additive only, see comment above.
                "labour_cost": float(labour["attributed_cost"]),
                "labour_is_attributed": labour["is_attributed"],
                "labour_days": labour["labour_days"],
                "labour_method": labour["method"],
                "total_direct_cost_with_labour": float(total_cost_with_labour),
                "gross_profit_with_labour": float(gross_profit_with_labour),
                "gross_margin_ratio_with_labour": round(margin_with_labour, 6),
            }
        return results

    @staticmethod
    def labour_cost_bulk(db: Session, orders: List[Order]) -> dict:
        """Family P0.45 - Labour Cost Attribution. Uses only data that
        genuinely already exists and is already the codebase's own
        established convention, not an invented rate:

        - Employee.daily_wage (the existing, authoritative daily-rate
          property - "matching the source workbook's formula",
          monthly_salary/26 - reused here, not recomputed a second
          time as its own inline division).
        - One labour-day per DISTINCT (employee_id, date) pair among
          this order's DailyTasks with status "DONE" - counting
          distinct days, not distinct tasks, so an employee with two
          finished tasks on the same day for the same order is not
          double-billed for that day.

        This is deliberately NOT based on ProductionOperation's
        actual_duration_minutes: mixing a whole-day count (from
        DailyTask) with a partial-day, minutes-based figure (from
        ProductionOperation) for the same employee on the same date
        risks double-counting one day's wage across two different
        units, and there is no existing hours-per-day convention
        anywhere in this codebase to safely convert minutes into a
        fraction of that day - inventing one would be exactly the
        "invent employee hourly rates" this family must not do.

        An order with no DONE, order-linked DailyTask work returns
        attributed_cost=0 with is_attributed=False - a real "no
        attributable labour found", never confused with "zero labour
        cost". Batched at 2 queries total regardless of order count,
        matching profitability_bulk's own performance pattern.
        Returns {order.id: {"attributed_cost": Decimal, "is_attributed": bool,
        "labour_days": int, "method": str}}."""
        if not orders:
            return {}
        order_ids = [o.id for o in orders]

        done_tasks = (
            db.query(DailyTask)
            .filter(DailyTask.order_id.in_(order_ids), DailyTask.status == "DONE")
            .all()
        )
        employee_ids = {t.employee_id for t in done_tasks}
        employees_by_id = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()} if employee_ids else {}

        # DISTINCT (order_id, employee_id, date) - a set, not a list,
        # so a second same-day task for the same employee on the same
        # order collapses into the same labour-day rather than adding
        # a second one.
        labour_days_by_order: dict = {}
        for t in done_tasks:
            key = (t.employee_id, t.date.date())
            labour_days_by_order.setdefault(t.order_id, set()).add(key)

        results = {}
        for order in orders:
            day_keys = labour_days_by_order.get(order.id, set())
            if not day_keys:
                results[order.id] = {
                    "attributed_cost": Decimal("0"), "is_attributed": False,
                    "labour_days": 0, "method": "No completed, order-linked task work found for this order.",
                }
                continue
            total = Decimal("0")
            for employee_id, _ in day_keys:
                employee = employees_by_id.get(employee_id)
                if not employee:
                    continue
                # Employee.daily_wage is the existing, authoritative
                # daily-rate property ("matching the source workbook's
                # formula") - reused here rather than recomputing
                # monthly_salary/26 a second time. It returns a float
                # (rounded to 2dp), so wrapped via str() before Decimal
                # to avoid a binary-float artifact leaking into a
                # financial figure.
                daily_rate = Decimal(str(employee.daily_wage))
                total += daily_rate
            results[order.id] = {
                "attributed_cost": total.quantize(Decimal("0.01")), "is_attributed": True,
                "labour_days": len(day_keys),
                "method": "Attributed from completed task-days (Employee.monthly_salary / 26 per distinct employee-day).",
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
