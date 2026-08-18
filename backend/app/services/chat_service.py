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
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.models.material import Material
from app.models.client import Client
from app.models.order import Order
from app.models.production_job import ProductionJob
from app.models.issue import Issue
from app.models.ai_workspace_report import AIWorkspaceReport
from app.services.order_service import OrderService
from app.models.purchase import Purchase
from app.models.employee import Employee
from app.models.user import User
from app.services.notification_service import NotificationService
from app.utils.id_generator import generate_unique_code, generate_short_id
from app.models.daily_task import DailyTask
from app.models.leave import Leave
from app.models.attendance import Attendance
from app.models.supplier import Supplier
from app.models.supplier_material import SupplierMaterial
from app.schemas.chat import ChatContext, ProposedAction

THIS_RECORD_WORDS = ["this order", "this material", "this client", "this employee", "this supplier",
                      "summarize", "summarise", "should i reorder", "reorder this", "compare this supplier"]
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

    return {"quantity": quantity, "description": description.strip(), "unit": unit, "destination": destination}


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
    ]
    for pattern, qtype in patterns:
        match = re.search(pattern, m)
        if match:
            text = match.group(1).strip().rstrip("?.")
            if text in ("material", "this material", "the material", "it"):
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
                {"id": t.id, "description": t.task_description, "reason": t.delay_reason or "No reason recorded"}
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
            reasons = ", ".join(f"{t.task_description} ({t.delay_reason or 'no reason recorded'})" for t in blocked_tasks[:3])
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
                task_code=code, business_id=generate_short_id(), date=datetime.utcnow(),
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

        material_action = ChatService._route_material_action(m, db, user_role)
        if material_action:
            return material_action

        if context and context.cart_items and any(w in m for w in ["optimize", "cheapest supplier", "best supplier"]):
            if user_role in ("master",):
                return ChatService._optimize_cart(db, context.cart_items)
            return "Supplier price comparison is available to master accounts only.", [], []

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
        thickness_match = re.search(r"(\d+(?:\.\d+)?\s*mm)", description)
        thickness = thickness_match.group(1) if thickness_match else None
        unit = (parsed["unit"] or "sheet").title() + "s"

        payload = {"name": guessed_name, "unit": unit, "thickness_size": thickness, "opening_stock": 0, "minimum_stock": 0}
        proposal = ProposedAction(
            action_type="create_material",
            summary=f"Create \"{guessed_name}\"" + (f" ({thickness})" if thickness else "") + f", unit: {unit}",
            payload=payload,
        )
        lines = ["I couldn't find an exact matching material. I interpreted this as:", guessed_name]
        if thickness:
            lines.append(f"Thickness: {thickness}.")
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

        if any(w in m for w in ["low stock", "reorder", "alert"]):
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
