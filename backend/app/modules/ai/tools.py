"""AI tool implementations - the read-only query functions Gemini can
call once ai_gateway.py's redaction/protocol layer has let a request
through, plus the shared entity-resolution helpers
(_resolve_single_material/_employee/_order/_task) both these tools and
ai_gateway.py's write-action dispatch use to look up a record by name
or code. Split out of the former single ai_gateway.py (which mixed
this query layer together with the Gemini protocol/redaction/dispatch
logic - a genuinely different, security-critical concern kept
together in ai_gateway.py, not split further here).

Each function does its own local model import (e.g. `from
app.modules.inventory.models import Material` inside the function body) rather
than importing at module level - a pattern already established
throughout the original file, kept as-is here rather than changed
during this split."""
from typing import List, Tuple

from sqlalchemy.orm import Session
from datetime import datetime

from app.modules.ai.security import sanitize_untrusted_text


def _resolve_single_material(db: Session, name: str):
    """shared by every
    WRITE tool that resolves a material by name. Confirmed via real
    demo data (docs/Woodful_demo_data.xlsx) that names like "HDHMR"
    genuinely match multiple distinct variant rows (18mm/12mm/6mm),
    each its own Material record. issue_stock/transfer_stock/
    adjust_stock previously all used .filter(...).first(), silently
    picking one - a genuine data-integrity risk for a write action
    (the wrong material's stock could be adjusted), not just an
    unhelpful answer the way it was for the read-only stock-lookup
    tool. Returns (material, None) on a clean single match, or
    (None, error_message) for both "not found" and "ambiguous" -
    ambiguity must block a write and ask, never silently pick one."""
    from app.modules.inventory.models import Material
    matches = db.query(Material).filter(Material.name.ilike(f"%{name}%")).order_by(Material.name).all()
    if not matches:
        return None, f"I couldn't find a material matching \"{name}\"."
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        return None, f"\"{name}\" matches more than one material ({names}) - which one did you mean?"
    return matches[0], None


def _tool_get_material_stock(db: Session, args: dict, user_role: str) -> str:
    from app.modules.inventory.models import Material
    name = args.get("material_name", "")
    matches = db.query(Material).filter(Material.name.ilike(f"%{name}%")).order_by(Material.name).all()
    if not matches:
        return f"I couldn't find a material matching \"{name}\"."

    def _describe(material) -> str:
        text = (
            f"{material.name}: {material.current_stock} {material.unit} in stock "
            f"(minimum {material.minimum_stock} {material.unit})"
        )
        if material.location_ref:
            text += f", stored at {material.location_ref.name}"
        elif material.location:
            text += f", stored at {material.location}"
        return text

    if len(matches) == 1:
        return _describe(matches[0]) + "."

    # genuinely confirmed via real demo
    # data that a name this broad (e.g. "HDHMR") matches multiple
    # distinct thickness/variant rows, each with its own stock. Never
    # silently pick one or merge them into one number -
    # list every match, so the user sees the real
    # breakdown and can naturally follow up ("and pre laminated?",
    # etc.) to narrow it down themselves.
    lines = [f"\"{name}\" matches {len(matches)} materials:"]
    lines.extend(f"- {_describe(m)}." for m in matches)
    return "\n".join(lines)


def _tool_search_orders(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.sales.models import Order
    from app.modules.clients.models import Client
    name = args.get("client_name", "")
    orders = (
        db.query(Order).join(Client, Order.client_id == Client.id)
        .filter(Client.name.ilike(f"%{name}%")).order_by(Order.order_date.desc()).limit(10).all()
    )
    if not orders:
        return f"I couldn't find any orders for a client matching \"{name}\".", []
    is_master = user_role in ("master",)
    records = [{
        "type": "Order", "label": o.order_code,
        "sublabel": f"{o.project_status} - Rs {float(o.order_value):,.0f}" if is_master else o.project_status,
        "path": f"/orders/{o.id}",
    } for o in orders]
    return f"Found {len(orders)} order(s) for {name}.", records


def _resolve_single_employee(db: Session, name: str):
    """Resolves an employee by name, applying the same ambiguity-safety
    principle as _resolve_single_material. A partial name match can genuinely match
    multiple employees in a real business (e.g. "Ravi" matching both
    "Ravi Kumar" and "Ravi Sharma"). Silently picking one risks
    assigning a task to, recording leave for, or - worst of all for
    send_task_email - emailing another employee's task details to the
    wrong person entirely, which would violate the rule that employees
    must not receive another employee's task information. Returns
    (employee, None) on a clean single match, or (None, error_message)
    for both "not found" and "ambiguous"."""
    from app.modules.hr.models import Employee
    matches = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).order_by(Employee.name).all()
    if not matches:
        return None, f"I couldn't find an employee matching \"{name}\"."
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        return None, f"\"{name}\" matches more than one employee ({names}) - which one did you mean?"
    return matches[0], None


def _tool_get_employee_tasks(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.operations.models import DailyTask
    from datetime import datetime
    name = args.get("employee_name", "")
    status_filter = (args.get("status_filter") or "all").lower()
    employee, error = _resolve_single_employee(db, name)
    if error:
        return error, []
    query = db.query(DailyTask).filter(DailyTask.employee_id == employee.id)
    if status_filter == "overdue":
        query = query.filter(DailyTask.due_date < datetime.utcnow(), DailyTask.status != "DONE")
    elif status_filter in ("doing", "done", "blocked"):
        query = query.filter(DailyTask.status == status_filter.upper() if status_filter != "doing" else "DOING")
    tasks = query.order_by(DailyTask.date.desc()).limit(10).all()
    if not tasks:
        return f"No matching tasks for {employee.name}.", []
    records = [{
        "type": "Task", "label": t.task_code, "sublabel": t.task_description, "path": f"/daily-tasks/{t.id}",
    } for t in tasks]
    return f"{employee.name} has {len(tasks)} matching task(s).", records


def _tool_search_clients(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.clients.models import Client
    name = args.get("name", "")
    clients = db.query(Client).filter(Client.name.ilike(f"%{name}%")).limit(10).all()
    if not clients:
        return f"I couldn't find any clients matching \"{name}\".", []
    records = [{
        "type": "Client", "label": c.name, "sublabel": c.phone, "path": f"/clients/{c.id}",
    } for c in clients]
    return f"Found {len(clients)} client(s) matching \"{name}\".", records


def _tool_get_upcoming_holidays(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.hr.models import CompanyHoliday
    from datetime import date
    holidays = (
        db.query(CompanyHoliday)
        .filter(CompanyHoliday.date >= date.today(), CompanyHoliday.is_working == False)  # noqa: E712
        .order_by(CompanyHoliday.date.asc()).limit(5).all()
    )
    if not holidays:
        return "No upcoming company holidays are on record.", []
    records = [{
        "type": "Holiday", "label": h.name, "sublabel": h.date.strftime("%d %b %Y"), "path": "/company-holidays",
    } for h in holidays]
    return f"{len(holidays)} upcoming holiday(s): " + ", ".join(f"{h.name} ({h.date.strftime('%d %b')})" for h in holidays), records


def _tool_get_low_stock_materials(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    """Reuses ChatService._low_stock directly - the exact same query
    the deterministic 'low stock' keyword match already uses - rather
    than duplicate it. This tool exists for phrasings that keyword
    list doesn't catch (Gemini is only ever reached when deterministic
    parsing found nothing), not as a second implementation of the same
    check. Passes the real caller's user_role through so a master user
    gets the same privileged "View Purchase History" action links
    they'd see from the deterministic path, not a degraded response."""
    from app.modules.ai.orchestration import ChatService
    text, _suggestions, records = ChatService._low_stock(db, user_role)
    return text, records


def _resolve_single_order(db: Session, code: str):
    """Resolves an order by code, applying the same ambiguity-safety
    principle as
    _resolve_single_material/_resolve_single_employee/
    _resolve_single_task. Order codes follow a year-sequential format
    ("WC-{year}-{sequential}", confirmed directly against the real
    generate_unique_code call in orders.py) and can genuinely collide
    on a short partial match across different years (e.g. "003"
    matching both "WC-2025-003" and "WC-2026-003")."""
    from app.modules.sales.models import Order
    matches = db.query(Order).filter(Order.order_code.ilike(f"%{code}%")).order_by(Order.order_code).all()
    if not matches:
        return None, f"I couldn't find an order matching \"{code}\"."
    if len(matches) > 1:
        codes = ", ".join(m.order_code for m in matches)
        return None, f"\"{code}\" matches more than one order ({codes}) - which one did you mean?"
    return matches[0], None


def _tool_get_order(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    code = args.get("order_code", "")
    order, error = _resolve_single_order(db, code)
    if error:
        return error, []
    client_name = order.client.name if order.client else "Unknown client"
    is_master = user_role in ("master",)
    text = f"{order.order_code} ({client_name}): {order.project_status}"
    if is_master:
        text += f", value Rs {float(order.order_value):,.0f}, balance Rs {float(order.balance):,.0f}"
    if order.delivery_date:
        text += f", delivery {order.delivery_date.strftime('%d %b %Y')}"
    records = [{
        "type": "Order", "label": order.order_code,
        "sublabel": f"{order.project_status} - Rs {float(order.order_value):,.0f}" if is_master else order.project_status,
        "path": f"/orders/{order.id}",
    }]
    return text + ".", records


def _tool_get_order_tasks(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.operations.models import DailyTask
    code = args.get("order_code", "")
    order, error = _resolve_single_order(db, code)
    if error:
        return error, []
    tasks = db.query(DailyTask).filter(DailyTask.order_id == order.id).order_by(DailyTask.date.desc()).limit(10).all()
    if not tasks:
        return f"No tasks are recorded against {order.order_code}.", []
    records = [{
        "type": "Task", "label": t.task_code, "sublabel": f"{t.task_description} ({t.status})", "path": f"/daily-tasks/{t.id}",
    } for t in tasks]
    return f"{order.order_code} has {len(tasks)} task(s) on record.", records


def _tool_get_estimate(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from app.modules.sales.models import Estimate
    code = args.get("estimate_code", "")
    estimate = db.query(Estimate).filter(Estimate.estimate_code.ilike(f"%{code}%")).first()
    if not estimate:
        return f"I couldn't find an estimate matching \"{code}\".", []
    client_name = estimate.client.name if estimate.client else "Unknown client"
    is_master = user_role in ("master",)
    if is_master:
        text = f"{estimate.estimate_code} for {client_name} - status: {estimate.status}, total Rs {float(estimate.total_cost):,.0f}."
        sublabel = f"{estimate.status} - Rs {float(estimate.total_cost):,.0f}"
    else:
        text = f"{estimate.estimate_code} for {client_name} - status: {estimate.status}."
        sublabel = estimate.status
    records = [{
        "type": "Estimate", "label": estimate.estimate_code, "sublabel": sublabel, "path": f"/estimates/{estimate.id}",
    }]
    return text, records


def _tool_get_order_payments(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    if user_role not in ("master",):
        return "Payment details are available to master accounts only.", []
    from app.modules.sales.models import Payment
    code = args.get("order_code", "")
    order, error = _resolve_single_order(db, code)
    if error:
        return error, []
    from sqlalchemy import func
    agg = db.query(func.count(Payment.id), func.sum(Payment.amount)).filter(Payment.order_id == order.id).first()
    payment_count, total = agg[0] or 0, float(agg[1] or 0)
    if payment_count == 0:
        return f"No payments recorded against {order.order_code}.", []
    payments = db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.date.desc()).limit(15).all()
    records = [{
        "type": "Payment", "label": p.receipt_code,
        "sublabel": f"Rs {float(p.amount):,.0f} - {p.payment_mode} - {p.date.strftime('%d %b %Y')}",
        "path": f"/orders/{order.id}",  # no per-payment detail route exists; the order page shows its payment history
    } for p in payments]
    return f"{order.order_code}: {payment_count} payment(s) totaling Rs {total:,.0f}.", records


def _resolve_single_task(db: Session, code: str):
    """Resolves a task by code, applying the same ambiguity-safety
    principle as
    _resolve_single_material/_resolve_single_employee. Task codes
    (e.g. "TSK-045") are shorter than order codes and genuinely more
    likely to have partial-match collisions (e.g. "45" matching both
    "TSK-045" and "TSK-450") in a business with more than a handful of
    tasks. complete_task and put_task_on_hold are both write actions -
    silently completing or holding the wrong task is a genuine data-
    integrity risk, not just an unhelpful answer."""
    from app.modules.operations.models import DailyTask
    matches = db.query(DailyTask).filter(DailyTask.task_code.ilike(f"%{code}%")).order_by(DailyTask.task_code).all()
    if not matches:
        return None, f"I couldn't find a task matching \"{code}\"."
    if len(matches) > 1:
        codes = ", ".join(m.task_code for m in matches)
        return None, f"\"{code}\" matches more than one task ({codes}) - which one did you mean?"
    return matches[0], None


def _tool_get_task(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    code = args.get("task_code", "")
    task, error = _resolve_single_task(db, code)
    if error:
        return error, []
    assignee = task.employee.name if task.employee else "Unassigned"
    text = f"{task.task_code}: \"{task.task_description}\" - {task.status}, assigned to {assignee}"
    if task.due_date:
        text += f", due {task.due_date.strftime('%d %b %Y')}"
    records = [{
        "type": "Task", "label": task.task_code, "sublabel": f"{task.status} - {assignee}", "path": f"/daily-tasks/{task.id}",
    }]
    return text + ".", records


def _tool_get_product(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    from sqlalchemy import or_
    from app.modules.catalog.models import Product
    query = args.get("product_query", "")
    product = db.query(Product).filter(
        or_(Product.product_code.ilike(f"%{query}%"), Product.name.ilike(f"%{query}%"))
    ).first()
    if not product:
        return f"I couldn't find a product matching \"{query}\".", []
    is_master = user_role in ("master",)
    status = "active" if product.is_active else "inactive"
    if is_master:
        price_text = f"Rs {float(product.selling_price):,.0f}" if product.selling_price is not None else "no price set"
        text = f"{product.product_code} - {product.name}: {price_text} per {product.unit}, {status}."
        sublabel = f"{product.product_code} - {price_text}"
    else:
        text = f"{product.product_code} - {product.name}: {status}."
        sublabel = product.product_code
    records = [{
        "type": "Product", "label": product.name, "sublabel": sublabel, "path": f"/products/{product.id}",
    }]
    return text, records


def _tool_get_order_documents(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    """Lists document metadata only - filename and description - never
    opens or returns actual file bytes, matching the same safe pattern
    already established for the deterministic document-search chatbot
    handler. "order" is confirmed not in documents.py's own
    SENSITIVE_PARENT_TYPES, so this is correctly open to any
    authenticated user without an additional role gate here."""
    from app.modules.documents.models import GenericDocument
    code = args.get("order_code", "")
    order, error = _resolve_single_order(db, code)
    if error:
        return error, []
    from sqlalchemy import func
    doc_count = db.query(func.count(GenericDocument.id)).filter(
        GenericDocument.parent_type == "order", GenericDocument.parent_id == order.id,
    ).scalar() or 0
    if doc_count == 0:
        return f"No documents are attached to {order.order_code}.", []
    docs = db.query(GenericDocument).filter(
        GenericDocument.parent_type == "order", GenericDocument.parent_id == order.id,
    ).order_by(GenericDocument.created_at.desc()).limit(15).all()
    records = [{
        "type": "Document", "label": d.original_filename, "sublabel": sanitize_untrusted_text(d.description) or "",
        "path": f"/orders/{order.id}",
    } for d in docs]
    return f"{order.order_code} has {doc_count} document(s): " + ", ".join(d.original_filename for d in docs) + ".", records


def _tool_search_documents(db: Session, args: dict, user_role: str) -> Tuple[str, List[dict]]:
    """Searches Woodful's own GenericDocument records by filename
    across all 5 parent types at once - never Drive's raw index
    directly - Gemini is never given direct search access to the
    entire Drive without authorization. This only ever surfaces
    documents Woodful's own database already knows about and has
    already applied its normal authorization rules to.

    Deliberately excludes ClientDocument/PaymentDocument (separate
    models with their own schemas) - scoped to match get_order_documents'
    existing coverage rather than risk getting cross-model permission
    logic wrong for a first version of this tool.

    Filters out "employee"/"purchase" results for non-master users,
    replicating documents.py's own SENSITIVE_PARENT_TYPES gate exactly -
    a broad cross-type search must not become a way to see sensitive
    document listings a normal user couldn't reach through the UI."""
    from app.modules.documents.models import GenericDocument
    query = args.get("filename_query", "")
    docs = db.query(GenericDocument).filter(
        GenericDocument.original_filename.ilike(f"%{query}%")
    ).order_by(GenericDocument.created_at.desc()).limit(15).all()

    if user_role not in ("master",):
        from app.modules.documents.api.routes import SENSITIVE_PARENT_TYPES as _SENSITIVE
        docs = [d for d in docs if d.parent_type not in _SENSITIVE]

    if not docs:
        return f"I couldn't find any documents matching \"{query}\".", []

    # parent_id is not a real FK (points to a different table per
    # parent_type - see the model's own docstring), so each match's
    # parent must be resolved individually per type for a meaningful
    # label/path rather than left as a bare ID.
    from app.modules.sales.models import Order
    from app.modules.inventory.models import Supplier
    from app.modules.hr.models import Employee
    from app.modules.catalog.models import Product
    from app.modules.inventory.models import Purchase
    resolvers = {
        "order": (Order, "order_code", "/orders"),
        "supplier": (Supplier, "name", "/suppliers"),
        "employee": (Employee, "name", "/employees"),
        "product": (Product, "name", "/products"),
        "purchase": (Purchase, "purchase_code", "/purchases"),
    }

    records = []
    summary_lines = []
    for d in docs:
        model_cls, label_attr, path_prefix = resolvers[d.parent_type]
        parent = db.query(model_cls).filter(model_cls.id == d.parent_id).first()
        parent_label = getattr(parent, label_attr) if parent else f"{d.parent_type} #{d.parent_id}"
        records.append({
            "type": "Document", "label": d.original_filename,
            "sublabel": f"{d.parent_type}: {parent_label}",
            "path": f"{path_prefix}/{d.parent_id}",
        })
        summary_lines.append(f"{d.original_filename} ({d.parent_type}: {parent_label})")

    return f"Found {len(docs)} document(s): " + "; ".join(summary_lines) + ".", records


READ_TOOL_DISPATCH = {
    "get_material_stock": _tool_get_material_stock,
    "search_orders": _tool_search_orders,
    "get_employee_tasks": _tool_get_employee_tasks,
    "search_clients": _tool_search_clients,
    "get_upcoming_holidays": _tool_get_upcoming_holidays,
    "get_low_stock_materials": _tool_get_low_stock_materials,
    "get_order": _tool_get_order,
    "get_order_tasks": _tool_get_order_tasks,
    "get_estimate": _tool_get_estimate,
    "get_order_payments": _tool_get_order_payments,
    "get_task": _tool_get_task,
    "get_product": _tool_get_product,
    "get_order_documents": _tool_get_order_documents,
    "search_documents": _tool_search_documents,
}
