"""Rule-based business-intelligence assistant. Answers common questions by
querying the current domain directly - not a real LLM integration. The
OPENAI_API_KEY setting already exists in core/config.py for a future
upgrade to real natural-language understanding; this keyword-matching
version is a working, testable placeholder for that.

Context-awareness: when the frontend passes a ChatContext (the record
the user is currently viewing), "this order" / "this material" style
questions are answered against that specific record instead of falling
through to a generic aggregate answer.

Propose-confirm actions: the assistant never modifies business data on
its own. When it recognizes a request to record a payment, it parses
the details into a ProposedAction and returns it alongside the reply -
the frontend shows this for explicit confirmation, and only then calls
the real POST /api/payments/ endpoint (which has its own RBAC and
audit logging - this service never bypasses either).

Structured results: queries that answer "which records" (not just "how
many") return a `records` list alongside the text - each one tagged
with enough to render a clickable card and link straight to the real
detail page, rather than a wall of prose the user has to go find the
records from themselves.
"""
import re
import difflib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.models.material import Material
from app.models.product import Product
from app.models.order_item import OrderItem
from app.models.estimate_line_item import EstimateLineItem
from app.models.client import Client
from app.models.estimate import Estimate
from app.models.order import Order
from app.models.generic_document import GenericDocument
from app.models.client_activity import ClientActivity
from app.services.ai_layer import sanitize_untrusted_text
from app.models.production_job import ProductionJob
from app.models.issue import Issue
from app.models.ai_workspace_report import AIWorkspaceReport
from app.services.order_service import OrderService
from app.models.purchase import Purchase
from app.models.employee import Employee
from app.models.user import User
from app.services.notification_service import NotificationService
from app.utils.id_generator import generate_unique_code, generate_business_id
from app.models.daily_task import DailyTask
from app.models.leave import Leave
from app.models.attendance import Attendance
from app.models.supplier import Supplier
from app.models.supplier_material import SupplierMaterial
from app.schemas.chat import ChatContext, ProposedAction
from app.utils.material_interpreter import extract_thickness, interpret_material_name
from app.services import analytics_service

THIS_RECORD_WORDS = ["this order", "this material", "this client", "this employee", "this supplier",
                      "summarize", "summarise", "should i reorder", "reorder this", "compare this supplier",
                      # Family 4 - "this project" is how the budget suggestion refers to an order
                      # (matching the Woodful UI's own "project" terminology), and "budget" on its
                      # own covers the case where context is already set from viewing an order page.
                      "this project", "budget"]
PAYMENT_INTENT_WORDS = ["record a payment", "record payment", "log a payment", "log payment", "add a payment"]
COMPLETE_TASK_WORDS = ["mark this done", "mark this task done", "mark this task as done", "mark as done",
                        "complete this task", "this is done", "task complete", "ye done kar", "ye complete"]
ASSIGN_TASK_PATTERN = re.compile(r"assign (.+?) to ([a-z]+)")
ORDER_BLOCKING_WORDS = ["what is blocking", "what's blocking", "kya problem hai", "kya scene hai",
                         "why is this delayed", "is this order at risk", "is this at risk"]
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


ADD_MATERIAL_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                              "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def parse_add_material_command(m: str) -> Optional[dict]:
    """Parses "add N <material description> [to <destination>]" style
    messages - "add one hdhmr sheet of 6mm in list", "add 5 hdhmr 18mm
    sheets to my purchase cart". Returns None if the message doesn't
    start with "add" at all (not this kind of command). Verified against
    every example phrase in the product brief before being wired into
    the chat service, not assumed correct from the regex alone."""
    if not m.startswith("add "):
        return None
    rest = m[4:]

    # Critical guard: "add" is a generic verb this parser used to claim
    # for ANY object, including ones that are a completely different
    # entity type - "add client Ramesh 9812345670" was silently parsed
    # as a material named "client Ramesh 9812345670" and proposed for
    # creation, because nothing here ever checked what was actually
    # being added. Bail out immediately for a message that's clearly
    # about client/customer, supplier/vendor, or another entity this
    # parser has no business touching - it falls through to that
    # entity's own handler (or, for client - which has no chat-write
    # path at all by design - to a normal conversational response)
    # instead of being silently reinterpreted as a material.
    other_entity_words = (
        "client", "customer", "supplier", "vendor", "employee", "staff",
        "estimate", "quotation", "order", "payment", "invoice",
    )
    filler_words = {"a", "an", "the", "new", "another"}
    words = [w.lower().rstrip(".,!?") for w in rest.strip().split()]
    # Skip leading filler ("add A NEW client..." must still be caught,
    # not just "add client...") - checked within the first few real
    # words, not the whole message, so a material description that
    # merely mentions "order" or "supplier" somewhere later isn't
    # wrongly blocked.
    significant_leading_words = [w for w in words if w not in filler_words][:2]
    if any(w in other_entity_words for w in significant_leading_words):
        return None

    qty_match = re.match(r"(\d+(?:\.\d+)?)\s+(.*)", rest)
    if qty_match:
        quantity = float(qty_match.group(1))
        rest = qty_match.group(2)
    else:
        word_match = re.match(r"(" + "|".join(ADD_MATERIAL_WORD_NUMBERS.keys()) + r")\s+(.*)", rest)
        if word_match:
            quantity = ADD_MATERIAL_WORD_NUMBERS[word_match.group(1)]
            rest = word_match.group(2)
        else:
            quantity = 1  # "add plywood" with no number stated - assume 1

    # "add 4 sheets to Ishu's project" is a different action (issue to a
    # project) this parser doesn't resolve - must not fall through to
    # material creation with the project reference leaking into the name.
    project_match = re.search(r"to\s+([a-z]+)'s\s+project", rest)
    if project_match:
        return {"destination": "project_issue", "project_name": project_match.group(1), "quantity": quantity}

    destination = "material_list"  # default when no destination is stated - matches the brief's own worked example
    dest_patterns = [
        (r"\s+to\s+(?:my\s+)?purchase\s+cart\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?cart\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?purchase\s+list\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?material\s+list\.?$", "material_list"),
        (r"\s+in\s+list\.?$", "material_list"),
        (r"\s+to\s+stock\.?$", "stock"),
    ]
    for pattern, dest in dest_patterns:
        if re.search(pattern, rest):
            destination = dest
            rest = re.sub(pattern, "", rest)
            break

    description = rest.strip().rstrip(".")
    description = re.sub(r"\s+sheets?\s+of\s+", " ", description)
    description = re.sub(r"\s+(sheets?|pairs?|pcs?|pieces?)$", "", description)
    unit_match = re.search(r"\b(sheets?|pairs?|pcs?|pieces?)\b", rest)
    unit = unit_match.group(1).rstrip("s") if unit_match else None
    description = description.strip()
    # "add 4 sheet" - no real material name given, just the bare unit
    # word left over. The suffix-strip above only handles a unit word
    # AFTER a real name ("hdhmr sheets" -> "hdhmr"); it can't catch the
    # case where the unit word IS the entire remaining text, since that
    # pattern requires a leading space that isn't there. Must not
    # confidently propose a material literally named "sheet" - clearing
    # it here lets the existing "I didn't catch what material" check
    # downstream correctly ask for clarification instead.
    if re.fullmatch(r"(sheets?|pairs?|pcs?|pieces?)", description):
        description = ""

    return {"quantity": quantity, "description": description, "unit": unit, "destination": destination}


def extract_material_query(m: str):
    """"How much HDHMR 18mm do we have", "which supplier supplied
    plywood" - extracts (query_type, material_text) so the assistant
    answers about the SPECIFIC named material, not a generic inventory
    summary. Returns None for a deictic reference ("this material",
    "the material") - that's page-context dependent and handled by
    _answer_from_context instead, not a literal name to search for.
    Tested against every example phrase in the product brief before
    being wired into the chat service."""
    patterns = [
        (r"how much (.+?) do we have", "stock"),
        (r"current stock of (.+?)$", "stock"),
        (r"stock of (.+?)$", "stock"),
        (r"which supplier (?:supplied|supplies) (?:this |the )?(.+?)$", "supplier"),
        (r"who (?:supplied|supplies) (?:this |the )?(.+?)$", "supplier"),
        (r"^(.+?)\s+kitn[ae]\s+(?:h|hai|hain|bacha|bache|pada|pade)\b", "stock"),
        (r"^stock\s+(.+?)$", "stock"),
    ]
    # Only for the new bare "stock X" pattern - "stock dashboard"/"stock
    # report" must fall through to the general stock summary, not
    # confidently claim it couldn't find a material named "dashboard".
    non_material_words = {"dashboard", "report", "summary", "levels", "status", "overview", "page"}
    for pattern, qtype in patterns:
        match = re.search(pattern, m)
        if match:
            text = match.group(1).strip().rstrip("?.")
            if text in ("material", "this material", "the material", "it") or text in non_material_words:
                return None
            return qtype, text
    return None


class ChatService:
    @staticmethod
    def _order_risk_workspace(db: Session, order_id: int, user_role: str, message: str):
        """"What is blocking this order" - a real multi-dimensional
        analysis combining only genuinely existing, queryable
        connections (tasks, production jobs, materials actually issued,
        delivery date) - never a fabricated materials-shortage figure,
        since EstimateLineItem has no link to the Material catalog at
        all, only a free-text description. The result is persisted as
        a real Woodful artifact (AIWorkspaceReport), not a one-off
        message that disappears, matching Section 10's "viewable,
        actionable, connected to Woodful data" requirement."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return "I couldn't find that order.", [], []
        is_privileged = user_role in ("master",)

        tasks = db.query(DailyTask).filter(DailyTask.order_id == order_id).all()
        blocked_tasks = [t for t in tasks if t.status == "BLOCKED"]
        open_tasks = [t for t in tasks if t.status != "DONE"]

        jobs = db.query(ProductionJob).filter(ProductionJob.order_id == order_id).all()
        incomplete_jobs = [j for j in jobs if j.status != "Completed"]

        issued_materials = db.query(Issue).filter(Issue.order_id == order_id).all()

        delivery_at_risk = False
        if order.delivery_date:
            days_left = (order.delivery_date - datetime.utcnow()).days
            delivery_at_risk = days_left <= 3 and (bool(open_tasks) or bool(incomplete_jobs))

        risk_level = "AT_RISK" if (blocked_tasks or delivery_at_risk) else "ON_TRACK"

        findings = {
            "order_code": order.order_code,
            "stage": order.project_status,
            "blocked_tasks": [
                {"id": t.id, "description": t.task_description, "reason": sanitize_untrusted_text(t.delay_reason) or "No reason recorded"}
                for t in blocked_tasks
            ],
            "open_task_count": len(open_tasks),
            "incomplete_production_jobs": len(incomplete_jobs),
            "materials_issued_count": len(issued_materials),
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "delivery_at_risk": delivery_at_risk,
        }
        if is_privileged:
            findings["pending_payment"] = float(order.balance or 0)

        report = AIWorkspaceReport(
            order_id=order_id, query_text=message, risk_level=risk_level,
            findings=json.dumps(findings), requested_by=None,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        lines = [f"{order.order_code} - {'AT RISK' if risk_level == 'AT_RISK' else 'ON TRACK'}"]
        if blocked_tasks:
            reasons = ", ".join(f"{t.task_description} ({sanitize_untrusted_text(t.delay_reason) or 'no reason recorded'})" for t in blocked_tasks[:3])
            lines.append(f"Blocked: {reasons}")
        if delivery_at_risk:
            lines.append("Delivery date is close with work still open.")
        if not blocked_tasks and not delivery_at_risk:
            lines.append("No blockers found - work is progressing normally.")

        records = [{
            "type": "Order", "label": order.order_code, "sublabel": findings["stage"],
            "path": f"/orders/{order.id}",
            "actions": [{"label": "View Order", "path": f"/orders/{order.id}"}],
        }]
        return "\n".join(lines), [], records

    @staticmethod
    def _complete_task_action(db: Session, user_role: str, current_employee_id: Optional[int],
                               context: Optional[ChatContext]):
        """"Mark this done" - resolves "this task" from page context
        (record_type/record_id), enforces the exact same ownership rule
        as PUT /api/daily-tasks/{id}/complete-and-assign-next, and
        performs the real update - never a second, chat-only version of
        this logic. Simple task actions may execute directly without a
        confirmation step, unlike financial actions such as payments."""
        if not context:
            return "I'm not sure which task you mean - open the task first, then ask me to mark it done.", [], []
        record_type, record_id = context.resolved()
        if record_type != "task" or not record_id:
            return "I'm not sure which task you mean - open the task first, then ask me to mark it done.", [], []

        task = db.query(DailyTask).filter(DailyTask.id == record_id).first()
        if not task:
            return "I couldn't find that task.", [], []
        if user_role not in ("master",) and task.employee_id != current_employee_id:
            return "You can only complete your own tasks.", [], []

        task.status = "DONE"
        task.completion_percent = 100
        db.add(task)
        db.commit()
        db.refresh(task)

        recipient = db.query(User).filter(User.employee_id == task.employee_id).first()
        if recipient:
            NotificationService.notify(
                db, notification_type="TASK_STATUS_CHANGED", severity="INFO",
                title="Task status: DONE", message=task.task_description,
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                dedup_key=f"task-status-{task.id}-DONE",
            )
        return f"Marked \"{task.task_description}\" as done.", [], [{
            "type": "Task", "label": task.task_description, "sublabel": "DONE", "path": f"/daily-tasks/{task.id}",
        }]

    @staticmethod
    def _assign_task_action(m: str, db: Session, context: Optional[ChatContext]):
        """"Assign wardrobe cutting to Pankaj" - creates a real task via
        the same fields/notification the POST /api/daily-tasks/ endpoint
        uses, not a second creation path. Task creation itself has
        always been open to any authenticated role (no ownership
        concept applies to creating a new task, unlike completing one),
        matching the real endpoint's existing permission."""
        match = ASSIGN_TASK_PATTERN.search(m)
        if not match:
            return None
        task_text = re.sub(r"^(the|a|an)\s+", "", match.group(1).strip())
        name = match.group(2).strip()

        employee = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).first()
        if not employee:
            return f"I couldn't find an employee matching \"{name}\".", [], []

        order_id = context.order_id if context else None
        for _ in range(5):
            code = generate_unique_code(db, DailyTask, "task_code", "TSK-")
            task = DailyTask(
                task_code=code, business_id=generate_business_id(db), date=datetime.utcnow(),
                employee_id=employee.id, order_id=order_id, task_description=task_text.capitalize(),
                status="TO DO",
            )
            db.add(task)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            db.refresh(task)
            recipient = db.query(User).filter(User.employee_id == employee.id).first()
            if recipient:
                NotificationService.notify(
                    db, notification_type="TASK_ASSIGNED", severity="INFO",
                    title="New task assigned", message=task.task_description,
                    recipient_user_id=recipient.id, related_entity_type="task",
                    related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                )
            return f"Assigned \"{task.task_description}\" to {employee.name}.", [], [{
                "type": "Task", "label": task.task_description, "sublabel": f"Assigned to {employee.name}",
                "path": f"/daily-tasks/{task.id}",
            }]
        return "Something went wrong creating that task - please try again.", [], []

    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user",
                         context: Optional[ChatContext] = None, current_employee_id: Optional[int] = None
                         ) -> Tuple[str, List[str], Optional[ProposedAction], Optional[dict], List[dict]]:
        m = message.lower()

        if any(w in m for w in COMPLETE_TASK_WORDS):
            text, suggestions, records = ChatService._complete_task_action(db, user_role, current_employee_id, context)
            return text, suggestions, None, None, records

        assign_result = ChatService._assign_task_action(m, db, context)
        if assign_result:
            text, suggestions, records = assign_result
            return text, suggestions, None, None, records

        if any(w in m for w in ORDER_BLOCKING_WORDS) and context:
            record_type, record_id = context.resolved_with_reference(m)
            if record_type == "order" and record_id:
                text, suggestions, records = ChatService._order_risk_workspace(db, record_id, user_role, message)
                return text, suggestions, None, None, records

        # Continuing a payment proposal started on a previous turn (the
        # frontend echoes back whatever `clarification` it was given).
        if context and context.pending and context.pending.get("type") == "record_payment":
            result = ChatService._continue_payment(m, user_role, context.pending, db)
            if result:
                return result

        if any(w in m for w in PAYMENT_INTENT_WORDS) and context and context.order_id:
            proposal = ChatService._propose_payment(m, db, user_role, context.order_id)
            if proposal:
                return proposal

        add_employee_action = ChatService._route_add_employee_action(m, db, user_role)
        if add_employee_action:
            return add_employee_action

        delete_product_action = ChatService._route_delete_product_action(m, db, user_role)
        if delete_product_action:
            return delete_product_action

        add_product_action = ChatService._route_add_product_action(m, db, user_role)
        if add_product_action:
            return add_product_action

        ambiguous_hindi_add = ChatService._route_ambiguous_hindi_add(m, db)
        if ambiguous_hindi_add:
            return ambiguous_hindi_add

        material_action = ChatService._route_material_action(m, db, user_role)
        if material_action:
            return material_action

        if context and context.cart_items and any(w in m for w in ["optimize", "cheapest supplier", "best supplier"]):
            if user_role in ("master",):
                text, suggestions, records = ChatService._optimize_cart(db, context.cart_items)
                return text, suggestions, None, None, records
            return "Supplier price comparison is available to master accounts only.", [], None, None, []

        text, suggestions, records = ChatService._dispatch(m, db, user_role, context, current_employee_id)
        return text, suggestions, None, None, records

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _route_add_employee_action(m: str, db: Session, user_role: str):
        """"add new employee arpit" was being silently swallowed by the
        material parser (any "add ..." message matched it unconditionally),
        creating a fake material literally named "new employee arpit".
        This is the specific, named collision from the product brief -
        a targeted disambiguation check for this one real bug, not an
        expansion into broad keyword-rule territory. Checked before the
        material parser so it never gets a chance to misfire here."""
        match = re.match(r"^add\s+(?:a\s+|an\s+|new\s+)*employee\s+(?:named\s+)?(.+)", m)
        if not match:
            return None
        name = match.group(1).strip().rstrip(".")
        if not name:
            return None
        if user_role not in ("master",):
            return "Creating employees requires a master account.", [], None, None, []

        existing = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).first()
        if existing:
            return (
                f"There's already an employee named {existing.name}.", [], None, None,
                [{"type": "Employee", "label": existing.name, "sublabel": existing.designation or "",
                  "path": f"/employees/{existing.id}"}],
            )

        display_name = " ".join(w.capitalize() for w in name.split())
        proposal = ProposedAction(
            action_type="create_employee",
            summary=f"Create employee \"{display_name}\"",
            payload={"name": display_name},
        )
        return f"Create a new employee named {display_name}?", [], proposal, None, []

    @staticmethod
    def _route_product_search(m: str, db: Session, user_role: str):
        """"find dining tables", "show products containing dining",
        "find PROD-001", "what is PROD-001", "show active dining
        products" (Family 104 section 43) - read-only, results always
        come from the actual Product Master, never invented."""
        code_match = re.search(r"\bprd-\d+\b", m, re.IGNORECASE)
        if code_match:
            product = db.query(Product).filter(Product.product_code.ilike(code_match.group(0))).first()
            if not product:
                return f"I couldn't find a product with code {code_match.group(0).upper()}.", [], None, None, []
            price = f"Rs {float(product.selling_price):,.2f}" if product.selling_price is not None else "no default rate set"
            lines = [f"{product.product_code} - {product.name}. {product.category or 'Uncategorized'}, "
                     f"unit: {product.unit}, {price}, {'Active' if product.is_active else 'Inactive'}."]
            return " ".join(lines), [], None, None, [{
                "type": "Product", "label": product.name, "sublabel": product.product_code,
                "path": f"/products/{product.id}",
            }]

        triggered = (
            any(w in m for w in ["find", "search product", "products containing"])
            or re.search(r"\bshow\b.*\bproducts?\b", m)
        )
        if not triggered:
            return None

        want_active_only = "active" in m
        # Strip the trigger phrasing to isolate the search term - a
        # short, deliberately simple extraction (not a full NLU parse)
        # matching the style of the other chat parsers in this file.
        # Word-boundary regex, not naive substring replace - "product"
        # is a substring of "products", so a plain .replace() would
        # mangle "products" into a stray "s" once "product" was
        # stripped out of the middle of it.
        term = m
        for phrase in ["find product", "find", "search product", "products containing", "show", "products", "product", "active"]:
            term = re.sub(rf"\b{re.escape(phrase)}\b", " ", term)
        term = re.sub(r"\s+", " ", term).strip()
        if not term or len(term) < 3:
            return "What product would you like to search for? Try at least 3 characters of the name.", [], None, None, []

        query = db.query(Product).filter(or_(
            Product.name.ilike(f"%{term}%"), Product.product_code.ilike(f"%{term}%"),
        ))
        if want_active_only:
            query = query.filter(Product.is_active == True)  # noqa: E712
        matches = query.order_by(Product.name).limit(8).all()
        if not matches:
            return f"No products found matching \"{term}\".", [], None, None, []

        records = [{
            "type": "Product", "label": p.name, "sublabel": p.product_code, "path": f"/products/{p.id}",
        } for p in matches]
        summary = "; ".join(f"{p.product_code} - {p.name}" for p in matches)
        return f"Found {len(matches)} product(s): {summary}.", [], None, None, records

    @staticmethod
    def _route_add_product_action(m: str, db: Session, user_role: str):
        """"Add a new product called 6 Seater Dining Table, category
        Dining, unit Piece, rate 25000 and GST 18%" (Family 104 section
        8) - same proposal-then-confirm architecture as
        _route_add_employee_action/_route_material_action: the chatbot
        never writes to the database directly, it builds a
        ProposedAction the frontend executes via the SAME authorized
        POST /api/products/ endpoint the UI form uses, after the user
        confirms - so validation, RBAC, and audit logging all happen
        exactly once, in one place."""
        match = re.match(r"^add\s+(?:a\s+|an\s+|new\s+)*product\s+(?:called\s+|named\s+)?(.+)", m, re.IGNORECASE)
        if not match:
            return None
        if user_role not in ("master",):
            return "Creating products requires a master account.", [], None, None, []

        rest = match.group(1)
        # "6 seater dining table, category dining, unit piece, rate 25000 and gst 18%"
        name_part = re.split(r",|\bcategory\b|\bunit\b|\brate\b|\bgst\b", rest, maxsplit=1)[0].strip().rstrip(".")
        if not name_part:
            return "What should the new product be called?", [], None, None, []

        category_match = re.search(r"category\s+([a-zA-Z ]+?)(?:,|\bunit\b|\brate\b|\bgst\b|$)", rest, re.IGNORECASE)
        unit_match = re.search(r"unit\s+([a-zA-Z ]+?)(?:,|\bcategory\b|\brate\b|\bgst\b|$)", rest, re.IGNORECASE)
        rate_match = re.search(r"rate\s+(?:rs\.?\s*)?([\d,]+)", rest, re.IGNORECASE)
        gst_match = re.search(r"gst\s+([\d.]+)\s*%?", rest, re.IGNORECASE)

        display_name = " ".join(w.capitalize() for w in name_part.split())

        # Duplicate check (Family 104 section 9) - blocked, not just
        # warned, for the chat path specifically: a short natural-
        # language message is a poor place to review a "possible
        # duplicate" match list, unlike the UI form's confirm dialog.
        existing = db.query(Product).filter(Product.name.ilike(f"%{name_part}%")).first()
        if existing:
            return (
                f"A product called \"{existing.name}\" ({existing.product_code}) already exists. Nothing created.",
                [], None, None, [{
                    "type": "Product", "label": existing.name, "sublabel": existing.product_code,
                    "path": f"/products/{existing.id}",
                }],
            )

        payload = {"name": display_name}
        summary_parts = [display_name]
        if category_match:
            payload["category"] = category_match.group(1).strip().title()
            summary_parts.append(f"category: {payload['category']}")
        if unit_match:
            payload["unit"] = unit_match.group(1).strip().title()
            summary_parts.append(f"unit: {payload['unit']}")
        if rate_match:
            payload["selling_price"] = float(rate_match.group(1).replace(",", ""))
            summary_parts.append(f"rate: Rs {payload['selling_price']:,.2f}")
        if gst_match:
            payload["gst_percent"] = float(gst_match.group(1))
            summary_parts.append(f"GST: {payload['gst_percent']}%")

        proposal = ProposedAction(
            action_type="create_product",
            summary="Create product " + ", ".join(summary_parts),
            payload=payload,
        )
        return f"Create a new product \"{display_name}\"" + (f" ({', '.join(summary_parts[1:])})" if len(summary_parts) > 1 else "") + "?", [], proposal, None, []

    @staticmethod
    def _route_delete_product_action(m: str, db: Session, user_role: str):
        """"Delete PROD-001" (Family 104 section 28/45) - Master only,
        checked here first (before the DB lookup even runs, so a non-
        master gets a clear refusal rather than a confusing "not
        found"); historically-referenced products are refused with a
        deactivation suggestion, matching the UI's own delete-route
        behavior exactly (same historical-reference queries)."""
        match = re.match(r"^delete\s+(prd-\d+)\b", m, re.IGNORECASE)
        if not match:
            return None
        if user_role not in ("master",):
            return "You do not have permission to delete products.", [], None, None, []

        code = match.group(1).upper()
        product = db.query(Product).filter(Product.product_code == code).first()
        if not product:
            return f"I couldn't find a product with code {code}.", [], None, None, []

        has_orders = db.query(OrderItem).filter(OrderItem.product_id == product.id).first() is not None
        has_estimates = db.query(EstimateLineItem).filter(EstimateLineItem.product_id == product.id).first() is not None
        if has_orders or has_estimates:
            return (
                f"{product.product_code} ({product.name}) is used in historical "
                f"{'orders' if has_orders else 'estimates'} and cannot be deleted. Deactivate it instead.",
                [], None, None, [{"type": "Product", "label": product.name, "sublabel": product.product_code,
                                   "path": f"/products/{product.id}"}],
            )

        proposal = ProposedAction(
            action_type="delete_product",
            summary=f"Permanently delete {product.product_code} - {product.name}",
            payload={"productId": product.id, "productCode": product.product_code},
        )
        return f"Permanently delete {product.product_code} - {product.name}? This cannot be undone.", [], proposal, None, []

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _route_client_order_query(m: str, db: Session, user_role: str, context: Optional[ChatContext]):
        """"patel ka payment?", "order sanket" - resolves a named client
        to their most recent order and reports its real status, rather
        than falling through to the generic company-wide summary that
        doesn't actually answer "how is THIS client's order doing".
        Returns None (not this kind of query) so process_message falls
        through to its other branches, matching the established
        _route_task_query convention."""
        name = ChatService._extract_client_name(m)
        if not name and context:
            # "isme payment kitna baki hai" - deictic follow-up to a
            # previously-discussed order, same mechanism already used
            # for the order-risk workspace.
            record_type, record_id = context.resolved_with_reference(m)
            if record_type == "order" and record_id and any(w in m for w in ["payment", "order", "baki", "pending"]):
                order = db.query(Order).filter(Order.id == record_id).first()
                if order:
                    return ChatService._describe_client_order(order, user_role)
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
        return ChatService._describe_client_order(order, user_role)

    @staticmethod
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

    @staticmethod
    def _route_sales_history_query(m: str, db: Session, user_role: str):
        """"patel sales history", "sanket's sales history" - a genuine
        summary derived from this client's actual orders and estimates,
        not a fabricated narrative. Financial totals are master-only,
        matching the same redaction already applied to order/estimate
        listings elsewhere - a non-master gets counts and status, not
        money."""
        if not any(w in m for w in ["sales history", "history"]):
            return None
        name = ChatService._extract_client_name(m)
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        name = ChatService._extract_client_name(m)
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

    @staticmethod
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

    @staticmethod
    def _delayed_projects(db: Session):
        """Family 12 - "which projects are delayed?" Reuses
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

    @staticmethod
    def _explain_expense_change(db: Session, user_role: str):
        """Family 12 - "why did expenses increase?" Grounded entirely in
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

    @staticmethod
    def _whats_changed_this_month(db: Session, user_role: str):
        """Family 12 - "what changed this month?" A cross-domain rollup
        built only from analytics_service.month_over_month_summary's
        real comparisons (revenue, expenses, blocked production, overdue
        tasks) - never a fabricated narrative. Financial lines are
        omitted entirely for a non-master viewer, not shown redacted."""
        is_privileged = user_role in ("master",)
        result = analytics_service.month_over_month_summary(db, is_privileged=is_privileged)
        return " ".join(result["summary_lines"]), [], []

    @staticmethod
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
        name = ChatService._extract_client_name(m)
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _summarize_supplier(m: str, db: Session, user_role: str):
        """"summarize supplier X" - a genuine summary derived from this
        supplier's real purchase history, not a fabricated narrative.
        On-time-vs-delayed ratio is computed only from purchases that
        actually have an expected_delivery_date set - a purchase never
        given a delivery expectation contributes to neither count."""
        if not any(w in m for w in ["summarize supplier", "supplier summary"]):
            return None
        match = re.search(r"(.+?)\s+supplier\s+summary", m) or re.search(r"summarize supplier\s+(.+?)$", m)
        if not match:
            return None
        name_text = match.group(1).strip()
        if name_text in ("", "summary"):
            return None

        suppliers = db.query(Supplier).filter(Supplier.name.ilike(f"%{name_text}%")).all()
        if not suppliers:
            all_names = [n for (n,) in db.query(Supplier.name).all()]
            close = difflib.get_close_matches(name_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
            if close:
                suppliers = db.query(Supplier).filter(Supplier.name.ilike(close[0])).all()
        if len(suppliers) != 1:
            return None
        supplier = suppliers[0]

        purchases = db.query(Purchase).filter(Purchase.supplier_id == supplier.id).all()
        if not purchases:
            return f"{supplier.name}: no purchases on record yet.", [], [{
                "type": "Supplier", "label": supplier.name, "sublabel": supplier.category or "",
                "path": f"/suppliers/{supplier.id}",
            }]

        with_expected = [p for p in purchases if p.expected_delivery_date]
        on_time = [p for p in with_expected if p.receipt_status == "Received"]
        lines = [f"{supplier.name}: {len(purchases)} purchase(s) on record."]
        if with_expected:
            lines.append(f"{len(on_time)}/{len(with_expected)} with a tracked delivery date were fully received.")
        if user_role in ("master",):
            total_value = sum(float(p.invoice_total or 0) for p in purchases)
            lines.append(f"Total purchase value Rs {total_value:,.2f}.")

        records = [{
            "type": "Supplier", "label": supplier.name, "sublabel": f"{len(purchases)} purchases", "path": f"/suppliers/{supplier.id}",
        }]
        return " ".join(lines), [], records

    @staticmethod
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
            ChatService._low_stock(db, user_role),
            ChatService._production_bottlenecks(db),
            ChatService._delayed_projects(db),
        ]:
            if records:
                sections.append(text)
                all_records.extend(records)
        if user_role in ("master",):
            for text, _, records in [
                ChatService._follow_up_suggestions(db),
                ChatService._delayed_deliveries(db),
            ]:
                if records:
                    sections.append(text)
                    all_records.extend(records)

        if not sections:
            return "Nothing needs attention right now - stock, production, projects, and deliveries all look clear.", [], []
        return " ".join(sections), [], all_records[:15]

    HINDI_ADD_VERBS = ["add kr do", "add kar do", "add karo", "add kro", "daal do", "daal dena", "daal dijiye"]
    HINDI_FILLER_WORDS = {"ki", "ka", "ke", "wali", "wala", "sheet", "sheets", "add"}

    @staticmethod
    def _route_ambiguous_hindi_add(m: str, db: Session):
        """"4 sheet add kr do 12mm ki" - Hindi/Hinglish often places the
        verb mid-sentence rather than "add X" at the start, a genuinely
        different shape from parse_add_material_command's English-order
        parsing. When the message has a quantity, "sheet", and a Hindi
        add-verb, but no word in it actually matches a real material
        (just a bare spec like "12mm" with nothing else), this asks
        which material rather than ever proposing to create or add
        anything - never a confident guess from a thickness number
        alone. Returns None (not this ambiguous shape, or a real
        material WAS found) so the message falls through normally."""
        has_qty = bool(re.search(r"\b\d+(?:\.\d+)?\b", m))
        has_sheet = bool(re.search(r"\bsheets?\b", m))
        has_hindi_verb = any(v in m for v in ChatService.HINDI_ADD_VERBS)
        if not (has_qty and has_sheet and has_hindi_verb):
            return None

        words = [w.strip(".,?!") for w in m.split()]
        candidate_words = [w for w in words if len(w) > 2 and w not in ChatService.HINDI_FILLER_WORDS
                            and not re.fullmatch(r"\d+(?:\.\d+)?", w)]
        found_real_material = False
        for word in candidate_words:
            like = f"%{word}%"
            if db.query(Material).filter(or_(
                Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
            )).first():
                found_real_material = True
                break

        if found_real_material:
            return None  # a real material name is present - let this fall through normally
        return "Konsi wali sheet? Please tell me the material - e.g. plywood, HDHMR, or laminate.", [], None, None, []

    @staticmethod
    def _route_material_action(m: str, db: Session, user_role: str):
        """Handles "add N <material> to my material list/cart" style
        commands (Section 1's critical bug). Searches across name,
        thickness_size, AND brand_grade for each significant word - a
        real material is frequently "HDHMR Board" with thickness_size
        "6mm" as a separate column, not "HDHMR 6mm" as one name string,
        so a name-only search would miss real matches."""
        parsed = parse_add_material_command(m)
        if not parsed:
            return None

        if parsed["destination"] == "project_issue":
            return (
                f"I can't yet issue material to a project through chat - please use the Issues "
                f"page to record what's being issued to {parsed['project_name'].title()}'s project.",
                [], None, None, [],
            )

        if parsed["destination"] == "stock":
            return (
                "I can't yet receive stock directly through chat - stock is recorded by creating "
                "a purchase on the Purchases page, which updates inventory automatically.",
                [], None, None, [],
            )

        description = parsed["description"]
        if not description:
            return (
                "I didn't catch what material you'd like to add. Try something like "
                "\"add 5 HDHMR 18mm sheets to my material list\".",
                [], None, None, [],
            )

        significant_words = [w for w in description.split() if len(w) > 2]
        query = db.query(Material)
        for word in significant_words:
            like = f"%{word}%"
            query = query.filter(or_(
                Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
            ))
        existing = query.first()

        if parsed["destination"] == "cart":
            if not existing:
                return (
                    f"I couldn't find an existing material matching \"{description}\". "
                    f"Would you like me to create it in Material Master first?",
                    [], None, None, [],
                )
            proposal = ProposedAction(
                action_type="add_to_cart",
                summary=f"Add {parsed['quantity']:g} {existing.unit} of {existing.name} to your purchase cart",
                payload={
                    "materialId": existing.id, "name": existing.name, "unit": existing.unit,
                    "rate": float(existing.average_rate), "quantity": parsed["quantity"],
                    "currentStock": existing.current_stock,
                },
            )
            return (
                f"I've prepared adding {parsed['quantity']:g} {existing.unit} of {existing.name} to your cart.",
                [], proposal, None, [],
            )

        # destination == "material_list"
        if existing:
            return (
                f"{existing.name} already exists in Material Master - current stock is "
                f"{existing.current_stock} {existing.unit}. Nothing to create.",
                [], None, None, [{
                    "type": "Material", "label": existing.name,
                    "sublabel": f"{existing.current_stock} {existing.unit} in stock",
                    "path": f"/materials/{existing.id}",
                }],
            )

        if user_role not in ("master",):
            return "Creating materials requires a master account.", [], None, None, []

        # A reasonable guess for the new material - never created
        # without explicit confirmation, matching the brief's exact UX.
        # Python's plain .title() mangles unit suffixes ("6mm" ->
        # "6Mm"), so capitalize word-by-word instead, leaving any token
        # that's not purely alphabetic untouched.
        guessed_name = " ".join(w.capitalize() if w.isalpha() else w for w in description.split())
        thickness = extract_thickness(description)
        unit = (parsed["unit"] or "sheet").title() + "s"

        # Same interpretation logic the material creation form's
        # "intelligent defaults" uses - only applied here (subcategory
        # pre-filled on the proposal) when it's actually confident;
        # otherwise the material is proposed uncategorized, same as
        # before, and the user assigns a category themselves.
        interpretation = interpret_material_name(db, description)
        payload = {"name": guessed_name, "unit": unit, "thickness_size": thickness, "opening_stock": 0, "minimum_stock": 0}
        summary_extra = ""
        if interpretation["confidence"] != "none":
            payload["subcategory_id"] = interpretation["subcategory_id"]
            summary_extra = f", category: {interpretation['subcategory_name']}"
        proposal = ProposedAction(
            action_type="create_material",
            summary=f"Create \"{guessed_name}\"" + (f" ({thickness})" if thickness else "") + f", unit: {unit}" + summary_extra,
            payload=payload,
        )
        lines = ["I couldn't find an exact matching material. I interpreted this as:", guessed_name]
        if thickness:
            lines.append(f"Thickness: {thickness}.")
        if interpretation["confidence"] != "none":
            lines.append(f"Category: {interpretation['subcategory_name']}.")
        lines.append(f"Unit: {unit}. Create this material?")
        return " ".join(lines), [], proposal, None, []

    @staticmethod
    def _dispatch(m: str, db: Session, user_role: str, context: Optional[ChatContext],
                  current_employee_id: Optional[int] = None) -> Tuple[str, List[str], List[dict]]:
        if context and any(w in m for w in THIS_RECORD_WORDS):
            contextual = ChatService._answer_from_context(m, db, user_role, context)
            if contextual:
                text, suggestions = contextual
                return text, suggestions, []

        task_result = ChatService._route_task_query(m, db, current_employee_id)
        if task_result:
            return task_result

        leave_result = ChatService._route_leave_query(m, db, current_employee_id, user_role)
        if leave_result:
            return leave_result

        salary_result = ChatService._route_salary_query(m)
        if salary_result:
            return salary_result

        if any(w in m for w in ["needs reordering", "replenishment", "to replenish"]):
            return ChatService._replenishment_requirements(db, user_role)
        if any(w in m for w in ["low stock", "reorder", "alert", "kam hai", "kam h", "material low", "materials low", "materials are low"]):
            return ChatService._low_stock(db, user_role)
        if "out of stock" in m or "out-of-stock" in m:
            return ChatService._out_of_stock(db, user_role)
        if any(w in m for w in ["purchased recently", "recent purchase", "bought recently"]):
            if user_role in ("master",):
                return ChatService._recent_purchases(db)
            return "Purchase information is available to master accounts only.", [], []
        if any(w in m for w in ["inventory value", "stock value", "purchase cost", "how much did we spend", "spent on"]):
            if user_role in ("master",):
                return ChatService._stock_summary(db, user_role)
            return "You don't have access to view this data.", [], []
        excel_query = ChatService._route_excel_via_chat(m, db, user_role)
        if excel_query:
            return excel_query
        client_order_query = ChatService._route_client_order_query(m, db, user_role, context)
        if client_order_query:
            return client_order_query
        sales_history_query = ChatService._route_sales_history_query(m, db, user_role)
        if sales_history_query:
            return sales_history_query
        estimate_summary = ChatService._route_estimate_summary(m, db, user_role, context)
        if estimate_summary:
            return estimate_summary
        order_products = ChatService._route_order_products(m, db, user_role, context)
        if order_products:
            return order_products
        product_search = ChatService._route_product_search(m, db, user_role)
        if product_search:
            return product_search
        next_action = ChatService._route_next_action(m, db, context)
        if next_action:
            return next_action
        if any(w in m for w in ["bottleneck", "production delay", "delayed production"]):
            return ChatService._production_bottlenecks(db)
        if any(w in m for w in ["delayed project", "delayed projects", "which projects are delayed", "projects are behind", "project late", "projects late", "late project"]):
            return ChatService._delayed_projects(db)
        if any(w in m for w in ["why did expenses", "why are expenses", "expenses increase", "expenses went up", "expenses go up"]):
            return ChatService._explain_expense_change(db, user_role)
        if any(w in m for w in ["what changed this month", "what changed", "changed this month"]):
            return ChatService._whats_changed_this_month(db, user_role)
        find_documents = ChatService._route_find_documents(m, db, user_role)
        if find_documents:
            return find_documents
        if (any(w in m for w in ["follow-up", "follow up", "followup"]) and any(w in m for w in ["due", "pending", "today"])) \
                or any(w in m for w in ["followed up", "who needs follow"]):
            if user_role in ("master",):
                return ChatService._follow_up_suggestions(db)
            return "Follow-up information is available to master accounts only.", [], []
        if any(w in m for w in ["delayed delivery", "delayed deliveries", "overdue delivery", "overdue deliveries"]):
            if user_role in ("master",):
                return ChatService._delayed_deliveries(db)
            return "Delivery information is available to master accounts only.", [], []
        supplier_summary = ChatService._summarize_supplier(m, db, user_role)
        if supplier_summary:
            return supplier_summary
        if any(w in m for w in ["needs attention", "what needs attention", "anything urgent", "daily briefing", "morning briefing"]):
            return ChatService._daily_briefing(db, user_role)
        if "usage" in m:
            usage_summary = ChatService._material_usage_summary(m, db)
            if usage_summary:
                return usage_summary
        material_query = ChatService._route_material_query(m, db)
        if material_query:
            return material_query
        if any(w in m for w in ["stock", "material", "inventory"]):
            return ChatService._stock_summary(db, user_role)
        if any(w in m for w in ["order", "project", "pipeline"]):
            return ChatService._orders_summary(db)
        if any(w in m for w in ["client", "customer", "find a client"]):
            return ChatService._clients_summary(db)
        if any(w in m for w in ["payment", "revenue", "pending amount", "balance", "owe"]):
            if user_role in ("master",):
                return ChatService._payments_summary(db)
            return "Financial information is available to master accounts only.", [], []
        if any(w in m for w in ["profit", "margin", "profitability"]):
            if user_role in ("master",):
                return ChatService._profitability_summary(db)
            return "Profit and margin information is available to master accounts only.", [], []
        if any(w in m for w in ["my attendance"]):
            if current_employee_id is None:
                return ("Your account isn't linked to an employee record, so I can't look up "
                        "your attendance."), [], []
            records = db.query(Attendance).filter(Attendance.employee_id == current_employee_id).order_by(
                Attendance.date.desc()
            ).limit(10).all()
            if not records:
                return "You have no attendance records yet.", [], []
            items = [{
                "type": "Attendance", "label": a.date.strftime("%d %b %Y"),
                "sublabel": a.attendance_status, "path": "/attendance",
            } for a in records]
            return f"Your last {len(records)} attendance record(s):", [], items
        if any(w in m for w in ["employee", "staff", "attendance"]):
            return ChatService._staff_summary(db)
        if any(w in m for w in ["pending purchase", "purchases pending"]):
            if user_role in ("master",):
                return ChatService._pending_purchases(db)
            return "Purchase information is available to master accounts only.", [], []
        if any(w in m for w in ["pending estimate", "estimates pending", "estimates awaiting", "follow up on estimate", "follow-up on estimate"]):
            if user_role in ("master",):
                return ChatService._pending_estimates(db)
            return "Estimate information is available to master accounts only.", [], []
        if "help" in m:
            return (
                "I can answer questions about stock/materials, orders, clients, payments "
                "(master only), and staff. Try asking about low stock, pending orders, "
                "or client count.",
                ["Check low stock", "Show pending orders", "How many clients?"], [],
            )
        return (
            "I didn't quite catch that. Try asking about stock, orders, clients, payments, or staff.",
            ["Check low stock", "Show pending orders", "Show staff summary"], [],
        )

    @staticmethod
    def _answer_from_context(m: str, db: Session, user_role: str, context: ChatContext):
        record_type, record_id = context.resolved_with_reference(m)
        if not record_type:
            return None

        if record_type == "order":
            order = db.query(Order).filter(Order.id == record_id).first()
            if not order:
                return None
            client_name = order.client.name if order.client else "Unknown client"
            if "budget" in m:
                # Family 4 - answers the "Why is this project running at a loss?" /
                # "How is this project's profitability tracking?" suggestion.
                # Woodful has no genuine planned/project-budget field - order_value
                # is the order's price, not a declared cost ceiling - so this never
                # claims a project is "over budget" (negative profit isn't the same
                # thing as exceeding a planned budget that doesn't exist here).
                # Reuses OrderService.profitability() (the exact same figures the
                # order detail page's own profitability panel already shows) rather
                # than a second, independently-derived calculation - and stays
                # behind the same master-only restriction that endpoint already
                # enforces, so a "user"-role viewer sees no financial figures here
                # either.
                if user_role not in ("master",):
                    return "Profitability details for this project aren't available to your account role.", []
                figures = OrderService.profitability(db, order)
                running_at_a_loss = figures["estimated_gross_profit"] < 0
                lines = [
                    f"{order.order_code}: order value Rs {figures['order_value']:,.2f}, "
                    f"actual direct costs so far Rs {figures['actual_direct_costs']:,.2f} "
                    f"(Rs {figures['material_cost']:,.2f} material + Rs {figures['project_expenses']:,.2f} expenses).",
                ]
                if running_at_a_loss:
                    lines.append(f"Costs so far exceed the order value by Rs {abs(figures['estimated_gross_profit']):,.2f}.")
                else:
                    lines.append(
                        f"Estimated gross profit so far: Rs {figures['estimated_gross_profit']:,.2f} "
                        f"({figures['gross_margin_percent'] * 100:.1f}% margin)."
                    )
                return " ".join(lines), []
            lines = [
                f"{order.order_code} for {client_name} - {order.project_type or 'project'}.",
                f"Stage: {order.project_status}. Progress: {order.progress_percent}%.",
                f"Order value: Rs {float(order.order_value):,.2f}.",
            ]
            if user_role in ("master",):
                lines.append(f"Received: Rs {float(order.total_received):,.2f}. Outstanding: Rs {float(order.balance):,.2f}.")
            if order.delivery_date:
                lines.append(f"Delivery date: {order.delivery_date.strftime('%d %b %Y')}.")
            return " ".join(lines), ["Record Payment", "Show order pipeline"]

        if record_type == "supplier":
            supplier = db.query(Supplier).filter(Supplier.id == record_id).first()
            if not supplier:
                return None
            total_spend = sum((float(p.invoice_total or 0) for p in supplier.purchases), 0.0)
            lines = [f"{supplier.name} ({supplier.supplier_code}): {len(supplier.purchases)} purchases on record."]
            if supplier.purchases:
                lines.append(f"Total spend: Rs {total_spend:,.2f}.")
            material_names = [sm.material.name for sm in supplier.supplier_materials if sm.material]
            if material_names:
                lines.append(f"Supplies: {', '.join(material_names[:5])}" + (" and more." if len(material_names) > 5 else "."))
            return " ".join(lines), []

        if record_type == "material":
            material = db.query(Material).filter(Material.id == record_id).first()
            if not material:
                return None
            if "reorder" in m:
                if material.current_stock <= material.minimum_stock:
                    shortfall = material.minimum_stock - material.current_stock
                    return (
                        f"Yes - {material.name} is at {material.current_stock} {material.unit}, "
                        f"at or below the reorder level of {material.minimum_stock} {material.unit}. "
                        f"Consider ordering at least {shortfall} {material.unit}.",
                        [],
                    )
                return (
                    f"Not yet - {material.name} has {material.current_stock} {material.unit} available, "
                    f"above the reorder level of {material.minimum_stock} {material.unit}.",
                    [],
                )
            return (
                f"{material.name} ({material.material_code}): {material.current_stock} {material.unit} available, "
                f"reorder level {material.minimum_stock} {material.unit}, status {material.stock_status}.",
                ["Should I reorder this?"],
            )

        if record_type == "client":
            client = db.query(Client).filter(Client.id == record_id).first()
            if not client:
                return None
            total_sales = sum((o.order_value for o in client.orders), 0)
            return (
                f"{client.name} ({client.client_code}): {len(client.orders)} orders, "
                f"Rs {float(total_sales):,.2f} in total order value.",
                [],
            )

        if record_type == "employee":
            employee = db.query(Employee).filter(Employee.id == record_id).first()
            if not employee:
                return None
            return (
                f"{employee.name} ({employee.employee_code}), {employee.department or 'no department'}. Status: {employee.status}.",
                [f"Show {employee.name.split()[0]}'s tasks"],
            )

        return None

    @staticmethod
    def _route_material_query(m: str, db: Session):
        """Handles "how much X do we have" and "which supplier supplied
        X" - resolves X against the real Material table (same
        significant-word ILIKE matching pattern as
        _route_material_action), not a generic inventory summary."""
        parsed = extract_material_query(m)
        if not parsed:
            return None
        query_type, material_text = parsed

        significant_words = [w for w in material_text.split() if len(w) > 2]
        if not significant_words:
            return None
        query = db.query(Material)
        for word in significant_words:
            like = f"%{word}%"
            query = query.filter(or_(
                Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
            ))
        material = query.first()
        if not material:
            # Exact substring search found nothing - try a typo-tolerant
            # fallback before giving up. "hdhr" is genuinely not a
            # substring of "HDHMR" (a letter is missing), which ILIKE
            # alone can never bridge - this is the specific, confirmed
            # gap from the brief's own "6mm hdhr kitna h" example.
            all_names = [n for (n,) in db.query(Material.name).all()]
            close = difflib.get_close_matches(material_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
            if close:
                material = db.query(Material).filter(Material.name.ilike(close[0])).first()
        if not material:
            return f"I couldn't find a material matching \"{material_text}\".", [], []

        if query_type == "stock":
            return (
                f"{material.name}: {material.current_stock} {material.unit} in stock "
                f"({material.stock_status}, reorder level {material.minimum_stock} {material.unit}).",
                [], [{
                    "type": "Material", "label": material.name,
                    "sublabel": f"{material.current_stock} {material.unit} - {material.stock_status}",
                    "path": f"/materials/{material.id}",
                }],
            )

        # query_type == "supplier"
        if material.primary_supplier:
            return (
                f"{material.name} is supplied by {material.primary_supplier.name}"
                + (f" ({material.primary_supplier.contact_person})" if material.primary_supplier.contact_person else "") + ".",
                [], [{
                    "type": "Supplier", "label": material.primary_supplier.name,
                    "sublabel": f"Supplies {material.name}", "path": f"/suppliers/{material.primary_supplier.id}",
                }],
            )
        return f"{material.name} has no primary supplier on record.", [], []

    @staticmethod
    def _stock_summary(db: Session, user_role: str = "user"):
        materials = db.query(Material).all()
        if user_role in ("master",):
            total_value = sum(m.stock_value for m in materials)
            return (
                f"You have {len(materials)} materials tracked, worth Rs {total_value:,.2f} in current stock.",
                ["Check low stock", "Show pending orders"], [],
            )
        return (
            f"You have {len(materials)} materials tracked.",
            ["Check low stock", "Show out of stock"], [],
        )

    @staticmethod
    def _route_leave_query(m: str, db: Session, current_employee_id: Optional[int], user_role: str = "user"):
        """"My leaves", "show Pankaj's leaves" - same real-data pattern as
        _route_task_query: "my" resolves through the actual
        User.employee_id link, a named person resolves through a live
        Employee.name query, never hard-coded. Works from any page,
        since it's checked unconditionally in _dispatch before any
        context-specific branch, not gated behind what record the user
        happened to be viewing when they opened the chat.

        Viewing a NAMED person's leaves is master-only, matching
        the exact same rule enforced on the real /api/leaves/ endpoint -
        the chatbot must not have looser permissions than the page it's
        standing in for."""
        if "leave" not in m:
            return None

        is_mine = any(w in m for w in ["my leave", "my leaves"])
        if is_mine:
            if current_employee_id is None:
                return ("Your account isn't linked to an employee record, so I can't look up "
                        "your leave records. Ask a master to link your account to your "
                        "employee profile."), [], []
            employee = db.query(Employee).filter(Employee.id == current_employee_id).first()
            return ChatService._leaves_for_employee(db, employee)

        name = ChatService._extract_employee_name_for_leaves(m)
        if name:
            if user_role not in ("master",):
                return "You can only view your own leave records.", [], []
            employee = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).first()
            if not employee:
                return f"I couldn't find an employee matching \"{name}\".", [], []
            return ChatService._leaves_for_employee(db, employee)

        return None

    @staticmethod
    def _extract_employee_name_for_leaves(m: str) -> Optional[str]:
        patterns = [
            r"([a-z]+)'s\s+leaves?",
            r"leaves?\s+.*?\b(?:for|of)\s+([a-z]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, m)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _leaves_for_employee(db: Session, employee):
        if not employee:
            return "I couldn't find that employee.", [], []
        leaves = db.query(Leave).filter(Leave.employee_id == employee.id).order_by(Leave.start_date.desc()).all()
        if not leaves:
            return f"{employee.name} has no leave records.", [], []
        records = [{
            "type": "Leave", "label": f"{leave.leave_type} - {leave.start_date.strftime('%d %b')} to {leave.end_date.strftime('%d %b %Y')}",
            "sublabel": f"{float(leave.days)} day(s) - {leave.status}",
            "path": "/leaves",
        } for leave in leaves[:10]]
        return f"{employee.name} has {len(leaves)} leave record(s).", [], records

    @staticmethod
    def _route_salary_query(m: str):
        """The chatbot never handles salary at all - no data, no
        permission branching, no employee lookup. Any mention of salary
        gets the same redirect to the Salary section for every role."""
        if "salary" not in m:
            return None
        return (
            "Salary details aren't available through chat - please visit the Salary section to view or download salary slips.",
            [], [{"type": "SalarySlip", "label": "Salary", "sublabel": "View salary slips", "path": "/salary-slips"}],
        )

    @staticmethod
    def _route_task_query(m: str, db: Session, current_employee_id: Optional[int]):
        """Handles every task-related question the assistant supports:
        "show my tasks", "show Pankaj's tasks", "what is Pankaj working
        on", "which of Pankaj's tasks are overdue", "which tasks are
        blocked". Employee names are resolved with a live query against
        Employee.name - never hard-coded, never a separate dataset -
        exactly the same table every other page reads from. Returns
        None (not a task query) so _dispatch falls through to its other
        branches."""
        is_task_query = any(w in m for w in ["task", "working on", "assigned"])
        if not is_task_query:
            return None

        wants_overdue = "overdue" in m
        wants_blocked = "blocked" in m

        is_mine = any(w in m for w in ["my task", "my tasks", "assigned to me", "i need to complete", "i need to do"])
        if is_mine:
            if current_employee_id is None:
                return ("Your account isn't linked to an employee record, so I can't look up "
                        "your tasks. Ask a master to link your account to your employee "
                        "profile."), [], []
            employee = db.query(Employee).filter(Employee.id == current_employee_id).first()
            return ChatService._tasks_for_employee(db, employee, overdue_only=wants_overdue)

        name = ChatService._extract_employee_name(m)
        if name:
            employee = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).first()
            if not employee:
                return f"I couldn't find an employee matching \"{name}\".", [], []
            return ChatService._tasks_for_employee(db, employee, overdue_only=wants_overdue)

        if wants_blocked:
            tasks = db.query(DailyTask).filter(DailyTask.status == "Blocked").all()
            return ChatService._format_task_results(tasks, f"{len(tasks)} tasks are currently blocked.")

        return None

    @staticmethod
    def _extract_employee_name(m: str) -> Optional[str]:
        """Regex only, no hard-coded names - just recognizes the shape of
        a possessive or prepositional reference to a person and pulls out
        whatever word is in that position."""
        patterns = [
            r"([a-z]+)'s\s+tasks?",
            r"tasks?\s+(?:are\s+|is\s+)?(?:for|assigned to)\s+([a-z]+)",
            r"what\s+is\s+([a-z]+)\s+working",
            r"overdue\s+for\s+([a-z]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, m)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _tasks_for_employee(db: Session, employee, overdue_only: bool = False):
        if not employee:
            return "I couldn't find that employee.", [], []
        query = db.query(DailyTask).filter(DailyTask.employee_id == employee.id)
        tasks = query.all()
        if overdue_only:
            today = datetime.utcnow().date()
            # Same definition of overdue used everywhere else this
            # applies (due date passed, not yet completed) - one
            # authoritative rule, not a chat-specific reinterpretation.
            tasks = [t for t in tasks if t.date.date() < today and t.status != "DONE"]
        label = f"{employee.name}'s {'overdue ' if overdue_only else ''}tasks"
        return ChatService._format_task_results(tasks, f"{len(tasks)} {label} found.")

    @staticmethod
    def _format_task_results(tasks, summary_text: str):
        records = [{
            "type": "Task", "label": t.task_description,
            "sublabel": f"{t.status} - {t.completion_percent}% complete"
                        + (f" - Priority: {t.priority}" if t.priority else ""),
            "path": f"/daily-tasks/{t.id}",
        } for t in tasks[:10]]
        return summary_text, [], records

    @staticmethod
    def _low_stock(db: Session, user_role: str):
        materials = db.query(Material).all()
        low = [m for m in materials if m.current_stock <= m.minimum_stock]
        if not low:
            return "All materials are above minimum stock levels.", [], []
        is_privileged = user_role in ("master",)
        records = []
        for m in low[:10]:
            actions = [{"label": "View Material", "path": f"/materials/{m.id}"}]
            if is_privileged:
                actions.append({"label": "View Purchase History", "path": f"/materials/{m.id}?tab=Purchases"})
            records.append({
                "type": "Material", "label": m.name,
                "sublabel": f"{m.current_stock}/{m.minimum_stock} {m.unit}",
                "path": f"/materials/{m.id}",
                "actions": actions,
            })
        return f"{len(low)} materials at or below minimum stock.", [], records

    @staticmethod
    def _replenishment_requirements(db: Session, user_role: str):
        """"what needs reordering" - the shortfall shown is honest
        arithmetic on two real stored values (minimum_stock minus
        current_stock), never a fabricated target level - this app has
        no "ideal stock" field to invent one from, and the AI must not
        pretend otherwise."""
        materials = db.query(Material).filter(Material.current_stock <= Material.minimum_stock).all()
        if not materials:
            return "Nothing currently needs reordering - all materials are above their minimum stock level.", [], []
        records = []
        for m in materials[:10]:
            shortfall = (m.minimum_stock or 0) - (m.current_stock or 0)
            sublabel = f"Need {shortfall} {m.unit} to reach minimum stock"
            if m.primary_supplier:
                sublabel += f" - usually supplied by {m.primary_supplier.name}"
            records.append({
                "type": "Material", "label": m.name, "sublabel": sublabel, "path": f"/materials/{m.id}",
            })
        return f"{len(materials)} material(s) need reordering to reach their minimum stock level.", [], records

    @staticmethod
    def _material_usage_summary(m: str, db: Session):
        """"hdhmr usage summary" - a genuine summary of real Issue
        records for this material, not a fabricated narrative.
        total_issued is confirmed kept in sync by stock_service.py on
        every issue - but it's gross issued, not net of any later
        returns, so it's labeled that way rather than implied to be
        "net consumed"."""
        patterns = [
            r"summarize\s+(.+?)\s+usage",
            r"usage\s+(?:of|for)\s+(.+?)$",
            r"(.+?)\s+usage(?:\s+summary)?\b",
        ]
        material_text = None
        for pattern in patterns:
            match = re.search(pattern, m)
            if match:
                material_text = match.group(1).strip()
                break
        if not material_text:
            return None

        significant_words = [w for w in material_text.split() if len(w) > 2]
        if not significant_words:
            return None
        query = db.query(Material)
        for word in significant_words:
            like = f"%{word}%"
            query = query.filter(or_(
                Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
            ))
        material = query.first()
        if not material:
            all_names = [n for (n,) in db.query(Material.name).all()]
            close = difflib.get_close_matches(material_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
            if close:
                material = db.query(Material).filter(Material.name.ilike(close[0])).first()
        if not material:
            return None

        issues = db.query(Issue).filter(Issue.material_id == material.id).order_by(Issue.date.desc()).all()
        if not issues:
            return f"{material.name} has never been issued.", [], []

        by_order = {}
        for i in issues:
            key = i.order.order_code if i.order else "No project"
            by_order[key] = by_order.get(key, 0) + float(i.quantity_issued)
        top_orders = sorted(by_order.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_summary = ", ".join(f"{code}: {qty:g} {material.unit}" for code, qty in top_orders)

        lines = [
            f"{material.name}: {float(material.total_issued or 0):g} {material.unit} issued in total across {len(issues)} issue(s).",
            f"Top consumers - {top_summary}.",
        ]
        records = [{
            "type": "Material", "label": material.name, "sublabel": f"{material.current_stock} {material.unit} in stock",
            "path": f"/materials/{material.id}",
        }]
        return " ".join(lines), [], records

    @staticmethod
    def _out_of_stock(db: Session, user_role: str):
        """Distinct from _low_stock - specifically materials at zero,
        not just at-or-below their reorder level."""
        materials = db.query(Material).all()
        zero = [m for m in materials if (m.current_stock or 0) <= 0]
        if not zero:
            return "No materials are currently out of stock.", [], []
        is_privileged = user_role in ("master",)
        records = []
        for m in zero[:10]:
            actions = [{"label": "View Material", "path": f"/materials/{m.id}"}]
            if is_privileged:
                actions.append({"label": "View Purchase History", "path": f"/materials/{m.id}?tab=Purchases"})
            records.append({
                "type": "Material", "label": m.name,
                "sublabel": f"0 {m.unit} - reorder level {m.minimum_stock} {m.unit}",
                "path": f"/materials/{m.id}",
                "actions": actions,
            })
        return f"{len(zero)} materials are completely out of stock.", [], records

    @staticmethod
    def _recent_purchases(db: Session):
        purchases = db.query(Purchase).order_by(Purchase.date.desc()).limit(10).all()
        if not purchases:
            return "No purchases recorded yet.", [], []
        records = [{
            "type": "Purchase", "label": p.material.name if p.material else "Material",
            "sublabel": f"{p.quantity} {p.unit} from {p.supplier.name if p.supplier else 'supplier'} on {p.date.strftime('%d %b %Y')}",
            "path": "/purchases",
        } for p in purchases]
        return f"Most recent {len(purchases)} purchases:", [], records

    @staticmethod
    def _orders_summary(db: Session):
        orders = db.query(Order).all()
        active = [o for o in orders if o.project_status != "Completed"]
        return (
            f"{len(orders)} total orders, {len(active)} still active.",
            ["Show pending payments", "Show client count"], [],
        )

    @staticmethod
    def _clients_summary(db: Session):
        count = db.query(Client).count()
        return f"You have {count} clients on file.", ["Show pending orders"], []

    @staticmethod
    def _payments_summary(db: Session):
        orders = db.query(Order).filter(Order.balance > 0).order_by(Order.balance.desc()).all()
        total_pending = sum(float(o.balance or 0) for o in orders)
        total_received = sum(float(o.total_received or 0) for o in db.query(Order).all())
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

    @staticmethod
    def _pending_purchases(db: Session):
        purchases = db.query(Purchase).filter(Purchase.payment_status != "Paid").all()
        if not purchases:
            return "No purchases are currently pending payment to suppliers.", [], []
        records = [{
            "type": "Purchase", "label": p.purchase_code,
            "sublabel": f"{p.supplier.name if p.supplier else 'Supplier'} - {p.payment_status}",
            "path": "/purchases",
        } for p in purchases[:10]]
        return f"{len(purchases)} purchases are pending payment to suppliers.", [], records

    @staticmethod
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

    @staticmethod
    def _staff_summary(db: Session):
        employees = db.query(Employee).filter(Employee.status == "Active").all()
        return f"{len(employees)} active employees on the team.", ["Show pending orders"], []

    @staticmethod
    def _optimize_cart(db: Session, cart_items):
        """For each cart line, finds the real cheapest available
        supplier (via SupplierMaterial pricing, falling back to the
        material's average_rate if no supplier is linked at all), groups
        the cart by chosen supplier, and reports genuine savings -
        cheapest total vs. what the same cart would cost if every item
        were bought at its most expensive available option. Never
        invents a price or a saving; a material with only one price
        source contributes zero to the savings figure, honestly."""
        supplier_groups = {}  # supplier_name -> [{material, quantity, rate, amount}]
        unresolved = []
        total_cheapest = Decimal("0")
        total_worst_case = Decimal("0")

        for item in cart_items:
            material = db.query(Material).filter(Material.id == item.material_id).first()
            if not material:
                continue
            links = db.query(SupplierMaterial).filter(
                SupplierMaterial.material_id == item.material_id, SupplierMaterial.supplier_price.isnot(None)
            ).all()
            qty = Decimal(str(item.quantity))

            if links:
                prices = [(link.supplier.name if link.supplier else "Unknown Supplier", link.supplier_price) for link in links]
                cheapest_name, cheapest_price = min(prices, key=lambda p: p[1])
                worst_price = max(p[1] for p in prices)
            elif material.average_rate:
                cheapest_name, cheapest_price = "Primary Supplier", material.average_rate
                worst_price = material.average_rate
            else:
                unresolved.append(material.name)
                continue

            amount = (cheapest_price * qty).quantize(Decimal("0.01"))
            total_cheapest += amount
            total_worst_case += (worst_price * qty).quantize(Decimal("0.01"))
            supplier_groups.setdefault(cheapest_name, []).append(
                {"material": material.name, "quantity": float(qty), "unit": material.unit, "amount": float(amount)}
            )

        if not supplier_groups:
            return "I couldn't find pricing for any of the materials in your cart yet.", [], []

        lines = [f"Estimated purchase value: Rs {float(total_cheapest):,.2f}, grouped by the cheapest available supplier per item."]
        savings = total_worst_case - total_cheapest
        if savings > 0:
            lines.append(f"Choosing the best price for each item saves Rs {float(savings):,.2f} compared to the most expensive option for each.")
        for supplier_name, items in supplier_groups.items():
            item_desc = ", ".join(f"{i['quantity']:g} {i['unit']} {i['material']}" for i in items)
            supplier_total = sum(i["amount"] for i in items)
            lines.append(f"{supplier_name}: {item_desc} - Rs {supplier_total:,.2f}.")
        if unresolved:
            lines.append(f"No pricing found for: {', '.join(unresolved)} - add a supplier price for these to include them.")

        return " ".join(lines), [], []

    @staticmethod
    def _profitability_summary(db: Session):
        """Reuses OrderService.profitability() - the exact same
        calculation the dashboard's "Gross Margin" figure already uses -
        rather than re-deriving order value/expenses/margin independently
        here, which risks the two disagreeing over time."""
        orders = db.query(Order).all()
        if not orders:
            return "No orders yet to calculate profitability from.", [], []

        rows = [OrderService.profitability(db, o) for o in orders]
        total_value = sum(r["order_value"] for r in rows)
        total_profit = sum(r["estimated_gross_profit"] for r in rows)
        total_material_cost = sum(r["material_cost"] for r in rows)
        overall_margin = (total_profit / total_value * 100) if total_value else 0.0

        lines = [
            f"Across {len(rows)} orders: total order value Rs {total_value:,.2f}, "
            f"material cost Rs {total_material_cost:,.2f}, "
            f"estimated gross profit Rs {total_profit:,.2f}, overall margin {overall_margin:.1f}%.",
        ]
        worst = min(rows, key=lambda r: r["gross_margin_percent"]) if rows else None
        if worst and worst["order_value"] > 0:
            lines.append(
                f"Lowest margin: {worst['order_id']} ({worst['client'] or 'client'}) "
                f"at {worst['gross_margin_percent'] * 100:.1f}%."
            )
        records = [{
            "type": "Order", "label": r["order_id"],
            "sublabel": f"{r['client'] or 'Client'} - Margin {r['gross_margin_percent'] * 100:.1f}%",
            "path": "/orders",
        } for r in sorted(rows, key=lambda r: r["gross_margin_percent"])[:5]]
        return " ".join(lines), [], records
