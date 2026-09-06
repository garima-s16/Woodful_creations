"""Cross-Module Business Risk + Business Decision Centre
(Family P0.49/P0.51).

Orchestrates already-authoritative domain signals into one unified,
prioritized "what needs my attention" view. Never recalculates a
domain-owned figure - every risk here traces back to a single
existing service call (OrderService.compute_order_health for orders;
SalarySlip.status for payroll) and is transformed into a structured,
explainable risk-item shape, not re-derived from raw tables. This
file is the one place that combines them; it is not a second
calculation engine for any of them.

Deliberately narrow scope for this family: Delivery (via Order
Health, which already folds in material/production/task signals -
P0.50) and Payroll (via SalarySlip.status). Standalone Inventory/
Procurement risk not already tied to an order, and full labour-cost
attribution, are not built here - there is no existing authoritative
service to consume for either yet, and inventing one would be exactly
the "second calculation engine" this family must not create (see
sections 9, 23, 26, 27).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.sales.models import Order
from app.modules.sales.order_service import OrderService
from app.modules.hr.models import SalarySlip, SalaryAdvance

# The order lifecycle's two terminal states (see sales/status_rules.py) -
# an order that has reached either one no longer needs cross-module
# attention; its health is settled, not "at risk" in a business sense.
_ORDER_TERMINAL_STATUSES = ("Completed", "Cancelled")

# compute_order_health's own 4-level model (P0.50) mapped onto the
# small severity vocabulary this layer uses (section 7) - a renaming
# for cross-module consistency, not a second scoring system.
_ORDER_RISK_TO_SEVERITY = {"CRITICAL": "CRITICAL", "AT_RISK": "HIGH", "WATCH": "MEDIUM"}

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _order_to_risk_item(order: Order, health: dict) -> dict:
    """Transforms one order's compute_order_health result into the
    P0.49 risk-item contract - the one place this shape is built, so
    _order_risk_items and get_risk_for_entity can never drift apart."""
    return {
        "risk_type": "DELIVERY",
        "severity": _ORDER_RISK_TO_SEVERITY.get(health["risk_level"], "LOW"),
        "entity_type": "order", "entity_id": order.id, "entity_code": order.order_code,
        "title": f"{order.order_code} needs attention",
        "reason": "; ".join(health["reasons"]),
        "evidence": health["evidence"],
        "business_impact": health["business_impact"],
        "recommended_action": health["next_action"]["description"] if health["next_action"] else None,
        "priority": health["risk_level"],
        "source_module": "sales",
        "action_path": f"/orders/{order.id}",
    }


def _order_risk_items(db: Session) -> list:
    """One risk item per open order whose compute_order_health is not
    ON_TRACK - the single authoritative per-order calculation, called
    once per open order (not per every order ever created), matching
    section 33's "active decision set" guidance rather than an
    unbounded historical scan. compute_order_health itself already
    uses batch-safe queries (StockService's material-requirement/
    reservation calculations), so this loop is bounded by the number
    of genuinely open orders, not a source of new N+1 queries within
    each iteration."""
    open_orders = db.query(Order).filter(Order.project_status.notin_(_ORDER_TERMINAL_STATUSES)).all()
    items = []
    for order in open_orders:
        health = OrderService.compute_order_health(db, order.id)
        if not health or health["risk_level"] == "ON_TRACK":
            continue
        items.append(_order_to_risk_item(order, health))
    return items


def _payroll_risk_items(db: Session) -> list:
    """A finalized-but-unpaid salary slip is real, existing, checkable
    data (SalarySlip.status, set by whoever runs payroll) - never an
    invented anomaly. Master-only: payroll figures are financial/
    confidential (sections 17, 21)."""
    pending = db.query(SalarySlip).filter(SalarySlip.status == "finalized").all()
    items = []
    for slip in pending:
        employee_name = slip.employee.name if slip.employee else "Unknown employee"
        items.append({
            "risk_type": "PAYROLL", "severity": "MEDIUM",
            "entity_type": "salary_slip", "entity_id": slip.id, "entity_code": slip.business_id,
            "title": f"Salary slip for {employee_name} ({slip.month} {slip.year}) is finalized but not paid",
            "reason": "Salary has been finalized but payment has not been recorded.",
            "evidence": [{"type": "payroll_pending", "month": slip.month, "year": slip.year}],
            "business_impact": "An employee's approved salary remains unpaid.",
            "recommended_action": "Record the salary payment.",
            "priority": "MEDIUM",
            "source_module": "hr",
            # No per-slip detail page exists - the list page shows the
            # same record with the actual approve/pay actions inline.
            "action_path": "/salary-slips",
        })
    return items


def _salary_advance_risk_items(db: Session) -> list:
    """A Pending salary advance request is a real, existing fact
    (Family P0.44 - built after this file's original P0.49 pass, added
    here once real data existed to consume - matching P0.44's own
    section 31: "prepare structured outputs... for P0.49/P0.51 to
    consume"). Deliberately does NOT flag every Approved-with-
    outstanding-balance advance as a risk - recovery can legitimately
    span several payroll months by design (see SalaryAdvance's own
    model comment), so an outstanding balance alone is expected
    behaviour, not an attention item; only a request still awaiting
    the Master's own decision is."""
    pending = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Pending").all()
    items = []
    for advance in pending:
        employee_name = advance.employee.name if advance.employee else "Unknown employee"
        items.append({
            "risk_type": "PAYROLL", "severity": "LOW",
            "entity_type": "salary_advance", "entity_id": advance.id, "entity_code": advance.business_id,
            "title": f"Salary advance request from {employee_name} is awaiting review",
            "reason": f"Requested {advance.requested_amount} on {advance.request_date.date().isoformat()}, not yet approved or rejected.",
            "evidence": [{"type": "salary_advance_pending", "requested_amount": float(advance.requested_amount)}],
            "business_impact": "The employee's request remains unresolved.",
            "recommended_action": "Review and approve or reject this salary advance request.",
            "priority": "LOW",
            "source_module": "hr",
            # No per-advance detail page exists - the list page shows
            # the same record with the actual approve/reject actions
            # inline.
            "action_path": "/salary-advances",
        })
    return items


def get_business_risks(db: Session, is_privileged: bool) -> dict:
    """P0.49 + P0.51 contract: one prioritized list of cross-module
    business risks plus a summary count - the same shape the REST API,
    frontend, and any future AI/chatbot consumer all read (section 19).
    is_privileged (MASTER) gates payroll/financial risk items; a
    non-privileged caller sees only operational (order-delivery) risk,
    matching sections 17/18/21's financial/HR confidentiality rule.
    Errors from one signal source must not silently look like "no
    risk" (section 35) - callers that need per-source error isolation
    should catch around the individual _*_risk_items() calls; this
    function itself does not swallow exceptions."""
    items = _order_risk_items(db)
    if is_privileged:
        items += _payroll_risk_items(db)
        items += _salary_advance_risk_items(db)

    items.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 9))

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in items:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1

    return {
        "total": len(items),
        "counts": counts,
        "risks": items,
        "generated_at": datetime.utcnow().isoformat(),
    }


def get_risk_for_entity(db: Session, entity_type: str, entity_id: int, is_privileged: bool) -> Optional[dict]:
    """Look up a single risk item by entity (section 19's AI contract -
    "why is this order at risk" needs one item, not the whole list).
    Recomputes directly via the same authoritative calculation rather
    than looping every open order or caching, so the answer is always
    current (section 34 - freshness) at the same cost as the existing
    per-order GET /api/orders/{id}/health endpoint - not a new N+1
    concern."""
    if entity_type == "order":
        order = db.query(Order).filter(Order.id == entity_id).first()
        if not order:
            return None
        health = OrderService.compute_order_health(db, entity_id)
        if not health or health["risk_level"] == "ON_TRACK":
            return None
        return _order_to_risk_item(order, health)
    if entity_type == "salary_slip" and is_privileged:
        matches = [r for r in _payroll_risk_items(db) if r["entity_id"] == entity_id]
        return matches[0] if matches else None
    if entity_type == "salary_advance" and is_privileged:
        matches = [r for r in _salary_advance_risk_items(db) if r["entity_id"] == entity_id]
        return matches[0] if matches else None
    return None
