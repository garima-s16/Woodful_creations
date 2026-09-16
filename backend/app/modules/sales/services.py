"""Sales services: chatbot-tool routing (payments/order-status/
client-order/sales-history/estimate-summary queries), OrderService
(order lifecycle business logic), line-item total computation,
whole-unit quantity validation, and estimate/order status-transition
rules. Combines the former services.py, order_service.py,
calculations.py, quantity_rules.py, and status_rules.py."""
import re
import json
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.modules.sales.models import Order, Estimate
from app.modules.clients.models import Client
from app.modules.ai.contracts import ChatContext, ProposedAction
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.modules.sales.models import Order, Payment
from app.modules.operations.models import ProjectExpense
from app.modules.operations.models import Issue, ProductionJob, DailyTask
from app.modules.inventory.models import Material
from app.modules.hr.models import Employee
from app.modules.sales.schemas import PaymentCreate
from app.modules.ai.contracts import sanitize_untrusted_text
from app.platform.ids import generate_unique_code, generate_business_id
from decimal import Decimal, ROUND_HALF_UP


# --- services.py ---
"""Chatbot sales-domain query/action handlers - client/order/estimate
lookups, sales history, payment proposal parsing, order-risk
workspace, and profitability summaries. Split out of the former
monolithic chat_service.py - see chat_inventory.py's docstring for
why."""

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

    # Deferred import: reporting/services.py imports OrderService from
    # this file at its own module level, so a top-level import of
    # AIWorkspaceReport here would be a genuine circular import (see
    # app.modules.ai.contracts.route_to_agent for the same pattern).
    from app.modules.reporting.services import AIWorkspaceReport
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


ORDER_STATUS_INTENT_WORDS = [
    "kaha pahucha", "kaha pahuncha", "kaha hai", "kaha tak pahucha", "kaha tak pahuncha",
    "kis stage", "kidhar", "order status", "order ka status", "status kya hai",
    "order progress", "kitna hua", "kitna ho gaya",
]


def _mentions_order_status_intent(m: str) -> bool:
    """ORDER_STATUS / ORDER_PROGRESS / WHERE_IS_ORDER intent - Hinglish
    and English phrasing covering "where is/has the order (reached/at
    what stage)", distinct from a plain "order" or "payment" mention
    (which _route_client_order_query already handles as a general
    order lookup). Requires "order" to also be mentioned for the
    English "where is"/"what is the status" phrasing, and for the
    bare Hindi "kaha hai"/"status kya hai" markers, since those words
    alone are too generic to safely trigger on."""
    if any(w in m for w in ["kaha pahucha", "kaha pahuncha", "kis stage", "kaha tak pahucha", "kaha tak pahuncha", "kidhar"]):
        return True
    if "order" not in m:
        return False
    if any(w in m for w in [
        "where is", "where has", "what is the status", "what's the status", "order status", "status of",
        # Bare Hindi forms ("kaha hai" = "where is", "status kya hai" =
        # "what is the status") - only checked once "order" is already
        # confirmed present above, same safety discipline as the
        # English markers just above.
        "kaha hai", "status kya hai",
    ]):
        return True
    return False


def _describe_order_status(order) -> str:
    """The real, authoritative current stage - project_status and
    progress_percent, the same fields _describe_client_order and the
    Orders List/Order Detail pages already use. Never a hardcoded or
    guessed value; if this order genuinely has no meaningful progress
    recorded yet, that is stated honestly rather than invented."""
    client_name = order.client.name if order.client else "This client"
    if order.progress_percent:
        return f"{client_name}'s order {order.order_code} is currently at \"{order.project_status}\" ({order.progress_percent}% complete)."
    return f"{client_name}'s order {order.order_code} is currently at \"{order.project_status}\"."


def _route_order_status_query(m: str, db: Session, user_role: str, context: Optional[ChatContext]):
    """Family 131-adjacent Woodful Assistant fix - "siddharth ka order
    kaha pahucha" and equivalent phrasing must answer the actual
    current stage, not the order's existence/code/value. Returns the
    full 5-tuple process_message expects
    (text, suggestions, proposed_action, clarification, records) - the
    clarification dict lets the client-name-ambiguity round-trip
    resume this exact intent on the next turn (see process_message's
    pending check), fixing the previous bug where a clarification
    reply lost the original question entirely."""
    if not _mentions_order_status_intent(m):
        return None
    name = _extract_client_name(m)
    if not name:
        return None
    return _resolve_and_describe_order_status(db, name)


def _resolve_and_describe_order_status(db: Session, name: str):
    """Returns the full 5-tuple process_message expects
    (text, suggestions, proposed_action, clarification, records) -
    proposed_action is always None here (this never proposes a data-
    modifying action); "clarification" is the position the pending
    dict belongs in, one slot later than it originally occupied."""
    clients = db.query(Client).filter(Client.name.ilike(f"%{name}%")).all()
    if not clients:
        return f"I couldn't find a client matching \"{name}\".", [], None, None, []
    if len(clients) > 1:
        options = ", ".join(c.name for c in clients[:5])
        pending = {"type": "order_status_query", "candidate_name": name}
        return (
            f"I found {len(clients)} clients matching \"{name}\": {options}. Which one did you mean?",
            [], None, pending, [],
        )

    orders = db.query(Order).filter(Order.client_id == clients[0].id).order_by(Order.order_date.desc()).all()
    if not orders:
        return f"{clients[0].name} has no orders on file yet.", [], None, None, []
    if len(orders) > 1:
        options = ", ".join(f"{o.order_code} ({o.project_status})" for o in orders[:5])
        pending = {"type": "order_status_query", "candidate_client_id": clients[0].id}
        return (
            f"{clients[0].name} has {len(orders)} orders: {options}. Which order did you mean?",
            [], None, pending, [],
        )

    return _describe_order_status(orders[0]), [], None, None, [{
        "type": "Order", "label": orders[0].order_code, "sublabel": orders[0].project_status,
        "path": f"/orders/{orders[0].id}",
    }]


def _continue_order_status_query(m: str, pending: dict, db: Session):
    """Resumes an order-status question across the clarification
    round-trip - the exact mechanism that was missing before this fix,
    which caused the follow-up ("Siddharth" alone, with no order-status
    keywords of its own) to lose the original intent and fall through
    to a generic tool instead. Returns the same 5-tuple shape as
    _resolve_and_describe_order_status (or None, meaning "could not
    resume - let the caller try other routes")."""
    if pending.get("candidate_client_id"):
        orders = db.query(Order).filter(Order.client_id == pending["candidate_client_id"]).order_by(Order.order_date.desc()).all()
        matched = next((o for o in orders if o.order_code.lower() in m or m.strip() in o.order_code.lower()), None)
        if not matched and len(orders) == 1:
            matched = orders[0]
        if not matched:
            options = ", ".join(o.order_code for o in orders[:5])
            return (
                f"I didn't catch which order - {options}?", [], None,
                {"type": "order_status_query", "candidate_client_id": pending["candidate_client_id"]}, [],
            )
        return _describe_order_status(matched), [], None, None, [{
            "type": "Order", "label": matched.order_code, "sublabel": matched.project_status,
            "path": f"/orders/{matched.id}",
        }]

    candidate_name = pending.get("candidate_name", "")
    clients = db.query(Client).filter(Client.name.ilike(f"%{candidate_name}%")).all()
    matched_client = next((c for c in clients if c.name.lower() in m or m.strip() in c.name.lower()), None)
    if not matched_client:
        return None
    return _resolve_and_describe_order_status(db, matched_client.name)


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


# --- order_service.py ---
"""Keeps Order.total_received / balance consistent with the Payment
register, and provides the profitability/dashboard aggregations, plus
the deterministic Order Health/Risk contract (Family 130 P0.1) that
both the chatbot and the plain Order Health API consume."""

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

        from app.modules.inventory.services import StockService
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
            from app.platform.audit import AuditLog
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
    def build_timeline(db: Session, order_id: int) -> Optional[dict]:
        """Family 137 feature 2 - Visual Build Timeline. A read-only
        presentation layer over existing Milestone and ProductionJob
        data - reuses compute_order_health for the order's own
        risk_level rather than inventing a second status engine
        (spec section 2: "do not create duplicate status systems or
        fake progress").

        Each milestone gets a status derived only from its own
        target_date/completed_date, plus - for the single next open
        milestone only - the order's real delivery risk:
          - completed: completed_date is set
          - delayed: not completed and target_date has already passed
          - at_risk: the next upcoming milestone, not yet delayed,
            while the order's own risk_level is AT_RISK/CRITICAL
            (never invented for a milestone that isn't next in line)
          - current: the next upcoming milestone otherwise
          - planned: every other still-ahead milestone

        production_summary is the exact same dict compute_order_health
        already computes (section 14) - never recalculated here."""
        from app.modules.operations.models import Milestone

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None

        health = OrderService.compute_order_health(db, order_id) or {}
        order_risk_level = health.get("risk_level", "ON_TRACK")

        # Sorted in Python (None-safe), matching the same
        # target_date-or-max convention already used for the
        # client-facing My Order milestone list (clients/portal_api.py).
        milestones = sorted(
            db.query(Milestone).filter(Milestone.order_id == order_id).all(),
            key=lambda m: m.target_date or datetime.max,
        )

        today = datetime.utcnow().date()
        open_milestones = [m for m in milestones if not m.completed_date]
        with_dates = [m for m in open_milestones if m.target_date]
        if with_dates:
            next_milestone_id = min(with_dates, key=lambda m: m.target_date).id
        elif open_milestones:
            next_milestone_id = open_milestones[0].id
        else:
            next_milestone_id = None

        milestone_views = []
        for m in milestones:
            if m.completed_date:
                status = "completed"
            elif m.target_date and m.target_date.date() < today:
                status = "delayed"
            elif m.id == next_milestone_id and order_risk_level in ("AT_RISK", "CRITICAL"):
                status = "at_risk"
            elif m.id == next_milestone_id:
                status = "current"
            else:
                status = "planned"
            milestone_views.append({
                "id": m.id, "business_id": m.business_id, "name": m.name,
                "target_date": m.target_date.isoformat() if m.target_date else None,
                "completed_date": m.completed_date.isoformat() if m.completed_date else None,
                "status": status, "remarks": m.remarks,
            })

        return {
            "order_id": order.id, "order_code": order.order_code,
            "project_status": order.project_status,
            "overall_risk_level": order_risk_level,
            "delivery_timing": health.get("delivery_timing"),
            "milestones": milestone_views,
            "production_summary": health.get("production_summary"),
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def evaluate_delivery_promise(db: Session, order_id: int, requested_date: datetime) -> Optional[dict]:
        """Family 137 feature 12 (cross-feature section 13's "Capacity-
        Aware Delivery Promise") - evaluates whether a requested
        delivery date is realistic using only genuinely existing
        signals; never a fabricated confidence score:

          - working calendar: hr.services.get_working_dates (the same
            weekday+holiday calculation payroll already relies on),
            not a naive calendar-day count
          - material availability: StockService.
            calculate_order_material_requirements - the same shortage
            calculation every other feature in this codebase already
            uses - plus the real expected_delivery_date of any pending
            purchase already covering part of the gap
          - production backlog: real ProductionOperation.
            estimated_duration_minutes already scheduled against each
            configured WorkCentre, compared to that work centre's own
            capacity_hours_per_day (the identical field the existing
            per-work-centre capacity endpoint already uses - not a
            second capacity concept)
          - historical context: how many of this order's own
            production jobs are already completed, surfaced as
            information only, never used to silently override anything

        Pure computation, no persistence - this is a PREDICTION plus a
        RECOMMENDATION, not a promise. Recording the human-selected
        final date is a separate, explicit write (see the
        POST /api/orders/{id}/delivery-promise route in api.py), never
        performed automatically here."""
        from app.modules.operations.models import WorkCentre, ProductionOperation
        from app.modules.procurement.models import Purchase
        from app.modules.hr.services import get_working_dates

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None

        today = datetime.utcnow().date()
        req_date = requested_date.date() if isinstance(requested_date, datetime) else requested_date
        reasons = []
        bottlenecks = []

        working_days = 0
        if req_date >= today:
            months_seen = set()
            working_dates_all = set()
            cursor = date(today.year, today.month, 1)
            # Walk month-by-month from today's month through the
            # requested month (inclusive) - bounded by the span between
            # the two real dates, never an unbounded loop.
            while (cursor.year, cursor.month) <= (req_date.year, req_date.month):
                if (cursor.year, cursor.month) not in months_seen:
                    months_seen.add((cursor.year, cursor.month))
                    working_dates_all |= get_working_dates(db, cursor.year, cursor.month)
                cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
            working_days = len([d for d in working_dates_all if today <= d <= req_date])
        else:
            reasons.append("Requested date is in the past.")

        material_ok = True
        material_bottleneck_date = None
        shortages = []
        try:
            reqs = StockService.calculate_order_material_requirements(db, order_id)
            shortages = [r for r in reqs["materials"] if r["shortage"] > 0]
        except HTTPException:
            shortages = []
        if shortages:
            material_ok = False
            shortage_material_ids = [r["material_id"] for r in shortages]
            pending = (
                db.query(Purchase)
                .filter(Purchase.material_id.in_(shortage_material_ids), Purchase.receipt_status != "Received",
                        Purchase.expected_delivery_date.isnot(None))
                .all()
            )
            if pending:
                material_bottleneck_date = max(p.expected_delivery_date for p in pending).date()
            for r in shortages[:3]:
                reasons.append(
                    f"Short {float(r['shortage']):g} {r['unit']} of {r['material_name']}"
                    + (" - no purchase placed yet" if not r["pending_purchase_quantity"] else " - awaiting a pending purchase")
                )
            bottlenecks.append({
                "type": "material_shortage",
                "detail": f"{len(shortages)} material(s) short against this order's requirements",
                "expected_resolved_date": material_bottleneck_date.isoformat() if material_bottleneck_date else None,
            })

        overloaded_centres = []
        if req_date >= today:
            work_centres = (
                db.query(WorkCentre)
                .filter(WorkCentre.is_active.is_(True), WorkCentre.capacity_hours_per_day.isnot(None))
                .all()
            )
            window_start = datetime.combine(today, datetime.min.time())
            window_end = datetime.combine(req_date, datetime.max.time())
            for wc in work_centres:
                scheduled_minutes = (
                    db.query(func.coalesce(func.sum(ProductionOperation.estimated_duration_minutes), 0))
                    .join(ProductionJob, ProductionJob.id == ProductionOperation.production_job_id)
                    .filter(
                        ProductionOperation.work_centre_id == wc.id,
                        ProductionOperation.status != "Completed",
                        ProductionJob.date >= window_start, ProductionJob.date <= window_end,
                    )
                    .scalar()
                ) or 0
                capacity_minutes = float(wc.capacity_hours_per_day) * 60 * max(working_days, 1)
                if capacity_minutes and scheduled_minutes > capacity_minutes:
                    overloaded_centres.append(wc.name)
            if overloaded_centres:
                bottlenecks.append({
                    "type": "capacity",
                    "detail": f"Work centre(s) already scheduled beyond capacity through this date: {', '.join(overloaded_centres)}",
                })
                reasons.append(f"Production backlog already exceeds capacity at: {', '.join(overloaded_centres)}")

        completed_jobs = [j for j in order.production_jobs if j.status == "Completed" and j.completion_date]
        historical_context = (
            f"{len(completed_jobs)} of {len(order.production_jobs)} production job(s) on this order are already completed."
            if order.production_jobs else "No production jobs recorded yet for this order."
        )

        if req_date < today:
            feasibility, confidence = "NOT_FEASIBLE", "LOW"
        elif not material_ok or overloaded_centres:
            feasibility, confidence = "AT_RISK", "MEDIUM"
        elif working_days < 2 and any(j.status != "Completed" for j in order.production_jobs):
            feasibility, confidence = "AT_RISK", "MEDIUM"
            reasons.append("Very little working time remains before the requested date.")
        else:
            feasibility = "FEASIBLE"
            confidence = "HIGH" if (material_ok and not overloaded_centres) else "MEDIUM"

        if not reasons:
            reasons.append("No shortage, dependency, or capacity conflict found from available data.")

        alternative_dates = []
        if feasibility != "FEASIBLE" and req_date >= today:
            push_days = 7
            if material_bottleneck_date and material_bottleneck_date > req_date:
                push_days = max(push_days, (material_bottleneck_date - req_date).days + 3)
            alternative_dates = [
                (req_date + timedelta(days=push_days)).isoformat(),
                (req_date + timedelta(days=push_days + 7)).isoformat(),
            ]

        return {
            "order_id": order_id, "order_code": order.order_code,
            "requested_date": req_date.isoformat(),
            "feasibility": feasibility,
            "confidence": confidence,
            "working_days_available": working_days,
            "reasons": reasons,
            "bottlenecks": bottlenecks,
            "alternative_dates": alternative_dates,
            "historical_context": historical_context,
            "current_promised_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "label": "PREDICTION",
            "generated_at": datetime.utcnow().isoformat(),
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


# --- calculations.py ---
"""Centralized discount/GST calculation - the stated requirement is:
"Calculations must be performed server-side... The backend must
recalculate: Line Total, Subtotal, Discount, Tax, Grand Total before
saving." Originally only implemented for Estimates; Orders had no
discount/tax fields at all (order_value was just a raw sum of line
items). Both now share this one implementation rather than risk the
two formulas drifting apart.
"""

def compute_totals(subtotal: Decimal, discount: Decimal, tax_percent: Decimal):
    """discount is an absolute currency amount (not a percentage) -
    matching the existing Estimate.discount field's established
    meaning; a caller wanting "10% off" computes the amount itself
    (subtotal * 10 / 100) before calling this, the same way the
    existing Estimate creation flow always has.

    taxable = subtotal - discount; tax is applied to the taxable
    amount, not the raw subtotal. Returns (tax_amount, grand_total).
    """
    taxable = subtotal - discount
    if taxable < 0:
        taxable = Decimal("0")
    tax_amount = (taxable * tax_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tax_amount, taxable + tax_amount


# --- quantity_rules.py ---
"""Countable-unit quantity validation - genuinely shared logic, not
duplicated. Used by app/modules/sales/schemas.py (re-exported from there for
existing importers) and directly by both app/modules/sales/imports.py
and app/modules/sales/imports.py - kept as its own module so all three
genuinely share one function rather than risk copies quietly drifting
apart.
"""

# --- status_rules.py ---
"""Server-side status lifecycle rules for Estimates and Orders.
Centralized here for the same reason ID generation and client
matching are centralized (see id_generator.py, client_matching.py):
one place that defines what's legal, reused by every entry point
(REST API, and implicitly denied to the AI/chat layer, which never
calls these directly), so the rule can
never drift or be bypassed by adding a second code path.

A frontend dropdown listing "valid" options is not validation - it's
a convenience. The real rule lives here and is enforced in
app/modules/sales/api.py / orders.py before any status write.
"""

ESTIMATE_STATUSES = {"draft", "sent", "approved", "rejected", "expired", "cancelled", "closed", "changes_requested"}


ESTIMATE_FINALIZED_STATUSES = {"approved", "rejected", "expired", "cancelled", "closed"}


ESTIMATE_TRANSITIONS = {
    # A draft can be sent for formal review, or decided on directly
    # (e.g. a verbal agreement, or staff marking it approved/rejected
    # immediately) - both paths are real, established usage (see
    # tests/modules/sales/test_estimate_order_validation_and_status.py, which predates this
    # rule and exercises draft -> approved and draft -> rejected
    # directly). "sent" is a real intermediate state, not a mandatory
    # gate every estimate must pass through.
    "draft": {"sent", "approved", "rejected", "cancelled"},
    # changes_requested: the client used the Client Approval Hub
    # (Family 137, feature 1) and asked for changes rather than
    # approving - see clients/portal_api.py. Staff addresses the
    # feedback and moves it back to "sent" (a revised estimate version
    # going out again), not directly to approved/rejected from here.
    "sent": {"approved", "rejected", "expired", "cancelled", "changes_requested"},
    "changes_requested": {"sent", "cancelled"},
    # An approved estimate can still be cancelled (the client backed out
    # before an order was actually created) but never revert to
    # draft/sent - and once it's been converted to an order, the order
    # itself becomes the record of what happened; the caller is
    # expected to check order_id separately before allowing this.
    "approved": {"cancelled"},
    "rejected": set(),
    "expired": set(),
    "cancelled": set(),
    "closed": set(),
}


def validate_estimate_status_transition(current: str, new: str) -> Optional[str]:
    """Returns an error message if the transition is not allowed, or
    None if it's fine. Setting status to its own current value is
    always a no-op success (an update that doesn't touch other fields
    but happens to re-send the current status shouldn't be treated as
    an illegal transition)."""
    if new not in ESTIMATE_STATUSES:
        return f"'{new}' is not a valid estimate status. Valid values: {', '.join(sorted(ESTIMATE_STATUSES))}."
    if current == new:
        return None
    allowed = ESTIMATE_TRANSITIONS.get(current, set())
    if new not in allowed:
        return f"An estimate cannot move from '{current}' to '{new}'."
    return None


ORDER_PROJECT_STATUSES = {
    "Enquiry", "Designing", "Approved", "Material Purchase", "Cutting", "Edge Banding",
    "Assembly", "Painting", "Ready for Dispatch", "Installation", "Completed", "On Hold", "Cancelled",
}


ORDER_SUB_STATUSES = {"Pending", "In Progress", "Completed"}


ORDER_TERMINAL_PROJECT_STATUSES = {"Cancelled"}


def validate_order_project_status_transition(current: str, new: str) -> Optional[str]:
    """Returns an error message if the caller is trying to move a
    terminal-status order to a different status, or None if that's not
    what's happening. Called in addition to validate_order_status_value
    (which only checks the new value is a real status name) - this
    checks the current value too, which that function deliberately does
    not have."""
    if current in ORDER_TERMINAL_PROJECT_STATUSES and new != current:
        return (f"This order is '{current}' and cannot be moved to '{new}'. "
                f"A cancelled order cannot be reopened through a status update.")
    return None


def validate_order_status_value(field_name: str, value: str) -> Optional[str]:
    """Order status fields don't have a meaningful linear transition
    order the way an estimate's approval flow does (a job can move
    Cutting -> On Hold -> Cutting again if a hold is lifted, for
    example) - so unlike estimates, this only validates that the value
    is one of the real, known values for that field, not a specific
    from-to transition. "Cancelled" is always reachable from any
    project_status (a job can be called off at any stage)."""
    if field_name == "project_status":
        if value not in ORDER_PROJECT_STATUSES:
            return f"'{value}' is not a valid order stage. Valid values: {', '.join(sorted(ORDER_PROJECT_STATUSES))}."
        return None
    if field_name in ("design_status", "execution_status", "delivery_status"):
        if value not in ORDER_SUB_STATUSES:
            return f"'{value}' is not a valid {field_name.replace('_', ' ')}. Valid values: {', '.join(sorted(ORDER_SUB_STATUSES))}."
        return None
    return None
