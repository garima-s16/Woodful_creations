"""Chatbot sales-domain query/action handlers - client/order/estimate
lookups, sales history, payment proposal parsing, order-risk
workspace, and profitability summaries. Split out of the former
monolithic chat_service.py - see chat_inventory.py's docstring for
why."""
import re
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.sales.models import Order, Estimate
from app.modules.clients.models import Client
from app.modules.reporting.models import AIWorkspaceReport
from app.modules.sales.order_service import OrderService
from app.modules.ai.schemas import ChatContext, ProposedAction

AMOUNT_PATTERN = re.compile(r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:rs\.?|rupees|inr)?", re.IGNORECASE)
PAYMENT_MODE_KEYWORDS = {
    "cash": "Cash",
    "upi": "UPI",
    "bank transfer": "Bank", "bank": "Bank", "neft": "Bank", "rtgs": "Bank",
    "credit card": "Credit Card", "card": "Credit Card",
}


def _detect_payment_mode(m: str) -> Optional[str]:
    for keyword, mode in PAYMENT_MODE_KEYWORDS.items():
        if keyword in m:
            return mode
    return None


def _order_risk_workspace(db: Session, order_id: int, user_role: str, message: str):
    """"What is blocking this order" - delegates the actual risk
    computation to OrderService.compute_order_health (the single
    authoritative Order Health/Risk contract, Family 130 P0.1), then
    adds the chat-specific behavior that function deliberately does
    NOT do: role-based financial redaction, persisting the result as a
    real Woodful artifact (AIWorkspaceReport, so it's viewable/
    actionable/connected to Woodful data, not a one-off message that
    disappears), and plain-text formatting for the chat reply."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return "I couldn't find that order.", [], []
    is_privileged = user_role in ("master",)

    findings = OrderService.compute_order_health(db, order_id)
    risk_level = findings["risk_level"]
    blocked_tasks = findings["blocked_tasks"]
    material_shortages = findings["material_shortages"]
    delivery_at_risk = findings["delivery_at_risk"]
    if is_privileged:
        findings["pending_payment"] = float(order.balance or 0)

    report = AIWorkspaceReport(
        order_id=order_id, query_text=message, risk_level=risk_level,
        findings=json.dumps(findings), requested_by=None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    delivery_timing = findings["delivery_timing"]
    business_impact = findings["business_impact"]

    risk_label = {"CRITICAL": "CRITICAL", "AT_RISK": "AT RISK", "WATCH": "WATCH", "ON_TRACK": "ON TRACK"}.get(risk_level, risk_level)
    lines = [f"{order.order_code} - {risk_label}"]
    if delivery_timing["has_delivery_date"]:
        lines.append(f"Delivery: {delivery_timing['urgency_text']}")
    if blocked_tasks:
        reasons = ", ".join(f"{t['description']} ({t['reason']})" for t in blocked_tasks[:3])
        lines.append(f"Blocked: {reasons}")
    if material_shortages:
        top = material_shortages[0]
        shortage_text = f"Short {top['shortage']:g} {top['unit']} of {top['material_name']}"
        if len(material_shortages) > 1:
            shortage_text += f" (+{len(material_shortages) - 1} other material(s))"
        if top["supplier_options"]:
            shortage_text += f" - {top['supplier_options'][0]['supplier_name']} can supply this"
        lines.append(shortage_text)
    if delivery_at_risk:
        lines.append("Delivery date is close with work still open.")
    if risk_level != "ON_TRACK":
        lines.append(business_impact)
    if not blocked_tasks and not delivery_at_risk and not material_shortages:
        lines.append("No blockers found - work is progressing normally.")

    records = [{
        "type": "Order", "label": order.order_code, "sublabel": findings["stage"],
        "path": f"/orders/{order.id}",
        "actions": [{"label": "View Order", "path": f"/orders/{order.id}"}],
    }]
    return "\n".join(lines), [], records


def _continue_payment(m: str, user_role: str, pending: dict, db: Session):
    if user_role not in ("master",):
        return "Recording payments requires a master account.", [], None, None, []

    order_id = pending.get("order_id")
    amount = pending.get("amount")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order or not amount:
        return None  # something is inconsistent - fall through to a fresh attempt

    mode = _detect_payment_mode(m)
    if not mode:
        return (
            "I still need a payment mode to proceed - Cash, UPI, Bank Transfer, or Credit Card?",
            [], None, pending, [],
        )

    payload = {
        "order_id": order_id,
        "date": datetime.utcnow().isoformat(),
        "payment_type": "Progress Payment",
        "payment_mode": mode,
        "amount": amount,
    }
    proposal = ProposedAction(
        action_type="record_payment",
        summary=f"Record a {mode} payment of Rs {float(amount):,.2f} against {order.order_code}",
        payload=payload,
    )
    return (
        f"Here's what I'll record: Rs {float(amount):,.2f} via {mode} against {order.order_code}. "
        f"Review and confirm - I won't record this without your confirmation.",
        [], proposal, None, [],
    )


def _propose_payment(m: str, db: Session, user_role: str, order_id: int):
    if user_role not in ("master",):
        return "Recording payments requires a master account.", [], None, None, []

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None

    amount_match = AMOUNT_PATTERN.search(m.replace(",", ""))
    if not amount_match:
        return (
            "I can help record a payment for this order, but I couldn't find an amount in your "
            "message. Try something like \"record a payment of 15000 for this order\".",
            [], None, None, [],
        )
    amount = amount_match.group(1)

    mode = _detect_payment_mode(m)
    if not mode:
        # Ask, per the brief - never default to Cash or any other mode.
        pending = {"type": "record_payment", "order_id": order_id, "amount": amount}
        return (
            f"Got it - Rs {float(amount):,.2f} against {order.order_code}. "
            f"What payment mode should I use - Cash, UPI, Bank Transfer, or Credit Card?",
            [], None, pending, [],
        )

    payload = {
        "order_id": order_id,
        "date": datetime.utcnow().isoformat(),
        "payment_type": "Progress Payment",
        "payment_mode": mode,
        "amount": amount,
    }
    proposal = ProposedAction(
        action_type="record_payment",
        summary=f"Record a {mode} payment of Rs {float(amount):,.2f} against {order.order_code}",
        payload=payload,
    )
    return (
        f"I've prepared a {mode} payment of Rs {float(amount):,.2f} against {order.order_code}. "
        f"Review the details and confirm to record it - I won't do this without your confirmation.",
        [], proposal, None, [],
    )


def _extract_client_name(m: str) -> Optional[str]:
    """Regex only, no hard-coded names - covers both Hinglish word
    orders ("patel ka order", "order patel") since either is
    natural depending on the speaker. Deliberately narrower than
    the employee-name extractor's patterns: "order"/"payment" are
    common enough English words that a looser match would trigger
    on unrelated sentences too often."""
    patterns = [
        r"([a-z]+)\s*(?:'s|ka|ki|ke)\s+(?:order|payment|history|sales history)",
        r"(?:order|payment|sales history|history)\s+(?:for\s+|of\s+)?([a-z]+)",
        r"([a-z]+)\s+(?:sales\s+)?history\b",
        r"next\s+(?:action\s+)?(?:on|for)\s+([a-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, m)
        if match:
            return match.group(1)
    return None


def _route_client_order_query(m: str, db: Session, user_role: str, context: Optional[ChatContext]):
    """"patel ka payment?", "order sanket" - resolves a named client
    to their most recent order and reports its real status, rather
    than falling through to the generic company-wide summary that
    doesn't actually answer "how is THIS client's order doing".
    Returns None (not this kind of query) so process_message falls
    through to its other branches, matching the established
    _route_task_query convention."""
    name = _extract_client_name(m)
    if not name and context:
        # "isme payment kitna baki hai" - deictic follow-up to a
        # previously-discussed order, same mechanism already used
        # for the order-risk workspace.
        record_type, record_id = context.resolved_with_reference(m)
        if record_type == "order" and record_id and any(w in m for w in ["payment", "order", "baki", "pending"]):
            order = db.query(Order).filter(Order.id == record_id).first()
            if order:
                return _describe_client_order(order, user_role)
        return None
    if not name:
        return None

    client = db.query(Client).filter(Client.name.ilike(f"%{name}%")).all()
    if not client:
        return None  # not a real client name - let other handlers try this message
    if len(client) > 1:
        options = ", ".join(c.name for c in client[:5])
        return f"I found {len(client)} clients matching \"{name}\": {options}. Which one did you mean?", [], []

    order = db.query(Order).filter(Order.client_id == client[0].id).order_by(Order.order_date.desc()).first()
    if not order:
        return f"{client[0].name} has no orders on file yet.", [], []
    return _describe_client_order(order, user_role)


def _describe_client_order(order, user_role: str):
    client_name = order.client.name if order.client else "Unknown client"
    lines = [f"{client_name}'s most recent order ({order.order_code}): {order.project_status}."]
    if user_role in ("master",):
        balance = float(order.balance or 0)
        if balance > 0:
            lines.append(f"Rs {balance:,.2f} is still pending.")
        else:
            lines.append("Fully paid.")
    records = [{
        "type": "Order", "label": order.order_code, "sublabel": order.project_status,
        "path": f"/orders/{order.id}",
    }]
    return " ".join(lines), [], records


def _route_sales_history_query(m: str, db: Session, user_role: str):
    """"patel sales history", "sanket's sales history" - a genuine
    summary derived from this client's actual orders and estimates,
    not a fabricated narrative. Financial totals are master-only,
    matching the same redaction already applied to order/estimate
    listings elsewhere - a non-master gets counts and status, not
    money."""
    if not any(w in m for w in ["sales history", "history"]):
        return None
    name = _extract_client_name(m)
    if not name:
        return None

    clients = db.query(Client).filter(Client.name.ilike(f"%{name}%")).all()
    if not clients:
        return None
    if len(clients) > 1:
        options = ", ".join(c.name for c in clients[:5])
        return f"I found {len(clients)} clients matching \"{name}\": {options}. Which one did you mean?", [], []

    client = clients[0]
    orders = db.query(Order).filter(Order.client_id == client.id).all()
    estimates = db.query(Estimate).filter(Estimate.client_id == client.id).all()

    lines = [f"{client.name}: {len(orders)} order(s), {len(estimates)} estimate(s) on record."]
    if user_role in ("master",):
        total_value = sum(float(o.order_value or 0) for o in orders)
        outstanding = sum(float(o.balance or 0) for o in orders)
        lines.append(f"Total order value Rs {total_value:,.2f}, of which Rs {outstanding:,.2f} is still outstanding.")

    history_records = [{
        "type": "Order", "label": o.order_code, "sublabel": o.project_status, "path": f"/orders/{o.id}",
    } for o in sorted(orders, key=lambda o: o.order_date or datetime.min, reverse=True)[:5]]
    return " ".join(lines), [], history_records


def _route_order_products(m: str, db: Session, user_role: str, context: Optional[ChatContext]):
    """"what products are in order WC-2026-001", "show order
    WC-2026-001", "products in this order" - lists the order's
    ACTUAL Order Items (each one's real linked Product where it has
    one), never invented or guessed. Resolves by explicit order
    code first, falling back to deictic context (viewing the
    order's own page)."""
    if not any(w in m for w in ["product", "what's in order", "whats in order", "show order", "order details"]):
        return None

    order = None
    code_match = re.search(r"\bwc-\d{4}-\d+\b", m, re.IGNORECASE)
    if code_match:
        order = db.query(Order).filter(Order.order_code.ilike(code_match.group(0))).first()
    elif "order" in m and context:
        record_type, record_id = context.resolved_with_reference(m)
        if record_type == "order" and record_id:
            order = db.query(Order).filter(Order.id == record_id).first()

    if not order:
        return None

    client_name = order.client.name if order.client else "Unknown client"
    if not order.items:
        lines = [f"{order.order_code} ({client_name}) has no itemized products on record."]
    else:
        item_descriptions = []
        for item in order.items:
            label = item.product.name if item.product else item.description
            item_descriptions.append(f"{label} (qty {item.quantity})")
        lines = [f"{order.order_code} ({client_name}) - status: {order.project_status}.",
                 "Items: " + "; ".join(item_descriptions) + "."]
    if user_role in ("master",) and order.order_value is not None:
        lines.append(f"Total Rs {float(order.order_value or 0):,.2f}.")
    if order.source_estimate_id:
        lines.append(f"Converted from estimate {order.source_estimate_code}.")

    records = [{
        "type": "Order", "label": order.order_code, "sublabel": order.project_status,
        "path": f"/orders/{order.id}",
    }]
    return " ".join(lines), [], records


def _route_estimate_summary(m: str, db: Session, user_role: str, context: Optional[ChatContext]):
    """"summarize estimate EST-001", or "summarize this estimate"
    while viewing one - a genuine summary of the estimate's actual
    line items and total, not a fabricated narrative. Resolves by
    explicit code first (works from anywhere), falling back to
    deictic context (works only while the relevant estimate page
    is open, or as a same-turn follow-up)."""
    if not any(w in m for w in ["summarize", "summary"]):
        return None

    estimate = None
    code_match = re.search(r"\best-\d+\b", m, re.IGNORECASE)
    if code_match:
        estimate = db.query(Estimate).filter(Estimate.estimate_code.ilike(code_match.group(0))).first()
    elif "estimate" in m and context:
        record_type, record_id = context.resolved_with_reference(m)
        if record_type == "estimate" and record_id:
            estimate = db.query(Estimate).filter(Estimate.id == record_id).first()

    if not estimate:
        return None

    lines = [f"{estimate.estimate_code} for {estimate.client.name if estimate.client else 'Unknown client'} - status: {estimate.status}."]
    item_count = len(estimate.line_items)
    lines.append(f"{item_count} line item(s).")
    if user_role in ("master",):
        lines.append(f"Total Rs {float(estimate.total_cost or 0):,.2f}.")
        if estimate.order_id:
            lines.append("Already converted to an order.")

    records = [{
        "type": "Estimate", "label": estimate.estimate_code, "sublabel": estimate.status,
        "path": f"/estimates/{estimate.id}",
    }]
    return " ".join(lines), [], records


def _orders_summary(db: Session):
    total = db.query(func.count(Order.id)).scalar() or 0
    active = db.query(func.count(Order.id)).filter(Order.project_status != "Completed").scalar() or 0
    return (
        f"{total} total orders, {active} still active.",
        ["Show pending payments", "Show client count"], [],
    )


def _clients_summary(db: Session):
    count = db.query(Client).count()
    return f"You have {count} clients on file.", ["Show pending orders"], []


def _payments_summary(db: Session):
    orders = db.query(Order).filter(Order.balance > 0).order_by(Order.balance.desc()).all()
    total_pending = sum(float(o.balance or 0) for o in orders)
    total_received = float(db.query(func.coalesce(func.sum(Order.total_received), 0)).scalar() or 0)
    if not orders:
        return f"No orders have an outstanding balance. Total received: Rs {total_received:,.2f}.", [], []
    records = [{
        "type": "Order", "label": o.order_code,
        "sublabel": f"{o.client.name if o.client else 'Client'} - Outstanding Rs {float(o.balance):,.2f}",
        "path": f"/orders/{o.id}",
    } for o in orders[:10]]
    return (
        f"{len(orders)} orders have outstanding payments, totaling Rs {total_pending:,.2f}.",
        [], records,
    )


def _pending_estimates(db: Session):
    """"sent" estimates awaiting a client response - the follow-up
    list a salesperson actually needs, not every estimate ever
    created."""
    estimates = db.query(Estimate).filter(Estimate.status == "sent").order_by(Estimate.created_at.desc()).all()
    if not estimates:
        return "No estimates are currently awaiting a client response.", [], []
    records = [{
        "type": "Estimate", "label": e.estimate_code,
        "sublabel": f"{e.client.name if e.client else 'Client'} - Rs {float(e.total_cost or 0):,.2f}",
        "path": f"/estimates/{e.id}",
    } for e in estimates[:10]]
    return f"{len(estimates)} estimates are awaiting a client response.", [], records


def _profitability_summary(db: Session):
    """Reuses OrderService.profitability() - the exact same
    calculation the dashboard's "Gross Margin" figure already uses -
    rather than re-deriving order value/expenses/margin independently
    here, which risks the two disagreeing over time."""
    orders = db.query(Order).all()
    if not orders:
        return "No orders yet to calculate profitability from.", [], []

    rows = list(OrderService.profitability_bulk(db, orders).values())
    total_value = sum(r["order_value"] for r in rows)
    total_profit = sum(r["estimated_gross_profit"] for r in rows)
    total_material_cost = sum(r["material_cost"] for r in rows)
    overall_margin = (total_profit / total_value * 100) if total_value else 0.0

    lines = [
        f"Across {len(rows)} orders: total order value Rs {total_value:,.2f}, "
        f"material cost Rs {total_material_cost:,.2f}, "
        f"estimated gross profit Rs {total_profit:,.2f}, overall margin {overall_margin:.1f}%.",
    ]
    worst = min(rows, key=lambda r: r["gross_margin_ratio"]) if rows else None
    if worst and worst["order_value"] > 0:
        lines.append(
            f"Lowest margin: {worst['order_id']} ({worst['client'] or 'client'}) "
            f"at {worst['gross_margin_ratio'] * 100:.1f}%."
        )
    records = [{
        "type": "Order", "label": r["order_id"],
        "sublabel": f"{r['client'] or 'Client'} - Margin {r['gross_margin_ratio'] * 100:.1f}%",
        "path": "/orders",
    } for r in sorted(rows, key=lambda r: r["gross_margin_ratio"])[:5]]
    return " ".join(lines), [], records
