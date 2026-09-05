"""Chatbot operations-domain query/action handlers - production
bottlenecks, delayed projects/deliveries, expense changes, document
search, Excel-import routing, and the daily briefing that combines
several of these into one summary. Split out of the former monolithic
chat_service.py - see chat_inventory.py's docstring for why.

_extract_client_name and _low_stock are genuinely cross-domain
dependencies (client-name parsing lives with the sales handlers that
mostly need it; low-stock lives with the inventory handlers) rather
than duplicated here - imported from their real domain modules."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.sales.models import Order
from app.modules.clients.models import Client, ClientActivity
from app.modules.operations.models import ProductionJob, DailyTask
from app.modules.inventory.models import Purchase
from app.modules.hr.models import Employee
from app.modules.documents.models import GenericDocument
from app.modules.ai.security import sanitize_untrusted_text
from app.modules.reporting import analytics_service
from app.modules.ai.schemas import ChatContext
from app.modules.sales.services import _extract_client_name
from app.modules.inventory.services import _low_stock


def _route_excel_via_chat(m: str, db: Session, user_role: str):
    """"pankaj ki August attendance Excel bana do" - resolves the
    employee and month, then returns a link to the SAME authorized
    /api/reports/attendance.xlsx endpoint every other export in the
    app uses. No AI-only export route exists or is created here -
    this is purely natural-language routing to the existing,
    already-permission-checked service. Master-only, matching that
    endpoint's own require_role("master") gate exactly."""
    if not any(w in m for w in ["excel", "spreadsheet", "xlsx"]):
        return None
    if "attendance" not in m:
        return None
    if user_role not in ("master",):
        return "Generating attendance reports requires a master account.", [], []

    month_names = ["january", "february", "march", "april", "may", "june",
                   "july", "august", "september", "october", "november", "december"]
    month = next((mn for mn in month_names if mn in m), None)
    if not month:
        return "Which month's attendance would you like as Excel?", [], []

    employees = db.query(Employee).all()
    employee = next((e for e in employees if e.name.lower() in m), None)
    if not employee:
        return f"Whose {month.title()} attendance would you like? I couldn't match a name in your message.", [], []

    year = str(datetime.utcnow().year)
    download_path = f"attendance.xlsx?employee_id={employee.id}&month={month.title()}&year={year}"
    return (
        f"Here's {employee.name}'s {month.title()} {year} attendance report.", [],
        [{"type": "Report", "label": f"{employee.name} - {month.title()} {year}", "sublabel": "Attendance Excel",
          "actions": [{"label": "Download Excel", "download_path": download_path}]}],
    )


def _route_next_action(m: str, db: Session, context: Optional[ChatContext]):
    """"what's next on this order" / "recommend next action for
    sanket" - replicates the exact "Next Action" definition already
    established on OrderDetailPage (earliest not-DONE task by date),
    rather than invent a different one. Resolves the order by client
    name or deictic context - no separate order-code parser, reusing
    what's already there for order/payment lookups."""
    if not any(w in m for w in ["next action", "what's next", "whats next", "recommend next"]):
        return None

    order = None
    name = _extract_client_name(m)
    if name:
        clients = db.query(Client).filter(Client.name.ilike(f"%{name}%")).all()
        if len(clients) == 1:
            order = db.query(Order).filter(Order.client_id == clients[0].id).order_by(Order.order_date.desc()).first()
    elif context:
        record_type, record_id = context.resolved_with_reference(m)
        if record_type == "order" and record_id:
            order = db.query(Order).filter(Order.id == record_id).first()

    if not order:
        return None

    next_task = db.query(DailyTask).filter(
        DailyTask.order_id == order.id, DailyTask.status != "DONE",
    ).order_by(DailyTask.date.asc()).first()

    if not next_task:
        return f"{order.order_code}: no open tasks - nothing outstanding to act on next.", [], [{
            "type": "Order", "label": order.order_code, "sublabel": order.project_status, "path": f"/orders/{order.id}",
        }]

    line = f"{order.order_code}: next up is \"{next_task.task_description}\""
    if next_task.employee:
        line += f" (assigned to {next_task.employee.name})"
    if next_task.status == "BLOCKED" and next_task.delay_reason:
        line += f" - currently BLOCKED: {sanitize_untrusted_text(next_task.delay_reason)}"
    line += "."
    records = [{
        "type": "Task", "label": next_task.task_description, "sublabel": next_task.status,
        "path": f"/daily-tasks/{next_task.id}",
    }]
    return line, [], records


def _production_bottlenecks(db: Session):
    """"production bottlenecks" - purely a count of real, currently
    Blocked jobs and jobs still open past their scheduled date,
    grouped by machine - never an inferred "why" or a fabricated
    cause, just what the actual records show."""
    today = datetime.utcnow().date()
    jobs = db.query(ProductionJob).filter(ProductionJob.status != "Completed").all()
    blocked = [j for j in jobs if j.status == "Blocked"]
    overdue = [j for j in jobs if j.date and j.date.date() < today]

    if not blocked and not overdue:
        return "No production bottlenecks right now - nothing is blocked or overdue.", [], []

    by_machine = {}
    for j in blocked + overdue:
        key = j.machine or "Unassigned"
        by_machine.setdefault(key, set()).add(j.id)
    ranked = sorted(by_machine.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]

    lines = [f"{len(blocked)} job(s) blocked, {len(overdue)} job(s) overdue and still open."]
    summary = ", ".join(f"{machine}: {len(job_ids)}" for machine, job_ids in ranked)
    lines.append(f"By machine - {summary}.")
    records = [{
        "type": "ProductionJob", "label": j.job_code, "sublabel": f"{j.machine or 'Unassigned'} - {j.status}",
        "path": f"/production-jobs/{j.id}",
    } for j in (blocked + overdue)[:10]]
    return " ".join(lines), [], records


def _delayed_projects(db: Session):
    """Handles "which projects are delayed?" Reuses
    analytics_service.projects_analytics's real on-hold/stalled
    detection (On Hold status, or zero progress 14+ days after
    order_date) rather than a separate ad-hoc query here - so the
    chatbot's answer can never disagree with what the Analytics
    page's own drill-down shows for the same question."""
    result = analytics_service.projects_analytics(db, is_privileged=True)
    delayed = result["delayed_projects"]
    if not delayed:
        return "No projects are currently delayed - nothing is on hold or stalled with zero progress.", [], []
    records = [{
        "type": "Order", "label": p["order_id"],
        "sublabel": f"{p['client'] or 'Client'} - {p['status']} ({p['progress_percent']}% complete)",
        "path": f"/orders/{p['id']}",
    } for p in delayed[:10]]
    return f"{len(delayed)} project(s) are delayed (on hold or stalled with no progress).", [], records


def _explain_expense_change(db: Session, user_role: str):
    """Handles "why did expenses increase?" Grounded entirely in
    analytics_service.expenses_analytics's real month-over-month
    category breakdown. If the data doesn't actually establish which
    category drove the change (e.g. too few expense records exist
    yet), this says so rather than inventing a cause."""
    if user_role not in ("master",):
        return "Expense information is available to master accounts only.", [], []
    result = analytics_service.expenses_analytics(db)
    change = result["expense_change_percent"]
    if change is None:
        return "There isn't enough expense history yet (no recorded expenses last month) to compare against.", [], []
    deltas = [d for d in result["category_change_this_month"] if d["delta"] != 0]
    if not deltas:
        return f"Expenses changed {change:+.1f}% this month, but no single category shows a real change - the totals moved evenly across categories.", [], []
    direction = "increased" if change >= 0 else "decreased"
    top = deltas[0]
    top_direction = "up" if top["delta"] > 0 else "down"
    lines = [f"Expenses {direction} {abs(change):.1f}% this month versus last month."]
    lines.append(
        f"The largest mover is '{top['category']}', {top_direction} Rs {abs(top['delta']):,.2f} "
        f"(Rs {top['last_month']:,.2f} \u2192 Rs {top['this_month']:,.2f})."
    )
    records = [{
        "type": "ExpenseCategory", "label": d["category"],
        "sublabel": f"Rs {d['last_month']:,.2f} \u2192 Rs {d['this_month']:,.2f}",
        "path": "/project-expenses",
    } for d in deltas[:5]]
    return " ".join(lines), [], records


def _whats_changed_this_month(db: Session, user_role: str):
    """Handles "what changed this month?" A cross-domain rollup
    built only from analytics_service.month_over_month_summary's
    real comparisons (revenue, expenses, blocked production, overdue
    tasks) - never a fabricated narrative. Financial lines are
    omitted entirely for a non-master viewer, not shown redacted."""
    is_privileged = user_role in ("master",)
    result = analytics_service.month_over_month_summary(db, is_privileged=is_privileged)
    return " ".join(result["summary_lines"]), [], []


def _route_find_documents(m: str, db: Session, user_role: str):
    """"find documents for sanket" - locates an order's attached
    files only after the same permission check the real
    /api/documents route itself applies (order is not in that
    route's SENSITIVE_PARENT_TYPES, so this is open) - the AI
    never gets a shortcut around document authorization just
    because it queries the database directly rather than calling
    its own HTTP API."""
    if not any(w in m for w in ["find document", "documents for", "show document", "files for"]):
        return None
    name = _extract_client_name(m)
    if not name:
        return None
    clients = db.query(Client).filter(Client.name.ilike(f"%{name}%")).all()
    if len(clients) != 1:
        return None
    order = db.query(Order).filter(Order.client_id == clients[0].id).order_by(Order.order_date.desc()).first()
    if not order:
        return f"{clients[0].name} has no orders on file yet.", [], []

    documents = db.query(GenericDocument).filter(
        GenericDocument.parent_type == "order", GenericDocument.parent_id == order.id,
    ).order_by(GenericDocument.created_at.desc()).all()
    if not documents:
        return f"No documents attached to {order.order_code} yet.", [], []
    records = [{
        "type": "Document", "label": d.original_filename, "sublabel": sanitize_untrusted_text(d.description) or "",
        "path": f"/orders/{order.id}",
    } for d in documents[:10]]
    return f"{len(documents)} document(s) attached to {order.order_code}.", [], records


def _follow_up_suggestions(db: Session):
    """"follow-ups due" - genuinely scheduled follow-ups
    (follow_up_date on or before today) logged against real client
    activities, never an inferred "who probably needs a call"
    without real data behind it."""
    today = datetime.utcnow().date()
    due = db.query(ClientActivity).filter(
        ClientActivity.follow_up_date.isnot(None), ClientActivity.follow_up_date <= datetime.utcnow(),
        ClientActivity.follow_up_done.is_(False),
    ).order_by(ClientActivity.follow_up_date.asc()).all()
    if not due:
        return "No follow-ups are due right now.", [], []
    records = [{
        "type": "Client", "label": a.client.name if a.client else "Client",
        "sublabel": f"Follow up ({a.follow_up_date.strftime('%d-%m-%Y')}): {sanitize_untrusted_text(a.summary[:60])}",
        "path": f"/clients/{a.client_id}",
    } for a in due[:10]]
    return f"{len(due)} follow-up(s) due.", [], records


def _delayed_deliveries(db: Session):
    """"delayed deliveries" - a purchase with a real
    expected_delivery_date that has passed, still not fully
    Received. Purchases with no expected_delivery_date set are
    never included - there's nothing to compare against, so no
    delay can be honestly claimed."""
    today = datetime.utcnow()
    purchases = db.query(Purchase).filter(
        Purchase.expected_delivery_date.isnot(None), Purchase.expected_delivery_date < today,
        Purchase.receipt_status != "Received",
    ).order_by(Purchase.expected_delivery_date.asc()).all()
    if not purchases:
        return "No deliveries are currently overdue.", [], []
    records = [{
        "type": "Purchase", "label": p.purchase_code,
        "sublabel": f"{p.supplier.name if p.supplier else 'Supplier'} - expected {p.expected_delivery_date.strftime('%d-%m-%Y')}",
        "path": "/purchases",
    } for p in purchases[:10]]
    word = "delivery" if len(purchases) == 1 else "deliveries"
    return f"{len(purchases)} {word} overdue.", [], records


def _daily_briefing(db: Session, user_role: str):
    """"what needs attention today?" - a genuine cross-module
    synthesis, not a new query: calls the same, already-proven
    handlers used elsewhere (low stock, production bottlenecks,
    delayed projects, and - master only, matching how each already
    gates itself individually - follow-ups due and delayed
    deliveries) and combines only the ones that actually found
    something. Never fabricates a summary when every domain is
    genuinely clear."""
    sections = []
    all_records = []
    for text, _, records in [
        _low_stock(db, user_role),
        _production_bottlenecks(db),
        _delayed_projects(db),
    ]:
        if records:
            sections.append(text)
            all_records.extend(records)
    if user_role in ("master",):
        for text, _, records in [
            _follow_up_suggestions(db),
            _delayed_deliveries(db),
        ]:
            if records:
                sections.append(text)
                all_records.extend(records)

    if not sections:
        return "Nothing needs attention right now - stock, production, projects, and deliveries all look clear.", [], []
    return " ".join(sections), [], all_records[:15]
