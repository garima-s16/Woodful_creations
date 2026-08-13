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
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.client import Client
from app.models.order import Order
from app.models.payment import Payment
from app.models.purchase import Purchase
from app.models.employee import Employee
from app.models.daily_task import DailyTask
from app.models.leave import Leave
from app.models.supplier import Supplier
from app.schemas.chat import ChatContext, ProposedAction

THIS_RECORD_WORDS = ["this order", "this material", "this client", "this employee", "this supplier",
                      "summarize", "summarise", "should i reorder", "reorder this", "compare this supplier"]
PAYMENT_INTENT_WORDS = ["record a payment", "record payment", "log a payment", "log payment", "add a payment"]
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


class ChatService:
    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user",
                         context: Optional[ChatContext] = None, current_employee_id: Optional[int] = None
                         ) -> Tuple[str, List[str], Optional[ProposedAction], Optional[dict], List[dict]]:
        m = message.lower()

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

        text, suggestions, records = ChatService._dispatch(m, db, user_role, context, current_employee_id)
        return text, suggestions, None, None, records

    @staticmethod
    def _continue_payment(m: str, user_role: str, pending: dict, db: Session):
        if user_role not in ("master", "manager"):
            return "Recording payments requires a master or manager account.", [], None, None, []

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
        if user_role not in ("master", "manager"):
            return "Recording payments requires a master or manager account.", [], None, None, []

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

        leave_result = ChatService._route_leave_query(m, db, current_employee_id)
        if leave_result:
            return leave_result

        if any(w in m for w in ["low stock", "reorder", "alert"]):
            return ChatService._low_stock(db)
        if any(w in m for w in ["stock", "material", "inventory"]):
            return ChatService._stock_summary(db)
        if any(w in m for w in ["order", "project", "pipeline"]):
            return ChatService._orders_summary(db)
        if any(w in m for w in ["client", "customer", "find a client"]):
            return ChatService._clients_summary(db)
        if any(w in m for w in ["payment", "revenue", "pending amount", "balance", "owe"]):
            if user_role in ("master", "manager"):
                return ChatService._payments_summary(db)
            return "Financial information is available to master/manager accounts only.", [], []
        if any(w in m for w in ["employee", "staff", "attendance"]):
            return ChatService._staff_summary(db)
        if any(w in m for w in ["pending purchase", "purchases pending"]):
            if user_role in ("master", "manager"):
                return ChatService._pending_purchases(db)
            return "Purchase information is available to master/manager accounts only.", [], []
        if "help" in m:
            return (
                "I can answer questions about stock/materials, orders, clients, payments "
                "(master/manager only), and staff. Try asking about low stock, pending orders, "
                "or client count.",
                ["Check low stock", "Show pending orders", "How many clients?"], [],
            )
        return (
            "I didn't quite catch that. Try asking about stock, orders, clients, payments, or staff.",
            ["Check low stock", "Show pending orders", "Show staff summary"], [],
        )

    @staticmethod
    def _answer_from_context(m: str, db: Session, user_role: str, context: ChatContext):
        if context.order_id:
            order = db.query(Order).filter(Order.id == context.order_id).first()
            if not order:
                return None
            client_name = order.client.name if order.client else "Unknown client"
            lines = [
                f"{order.order_code} for {client_name} - {order.project_type or 'project'}.",
                f"Stage: {order.project_status}. Progress: {order.progress_percent}%.",
                f"Order value: Rs {float(order.order_value):,.2f}.",
            ]
            if user_role in ("master", "manager"):
                lines.append(f"Received: Rs {float(order.total_received):,.2f}. Outstanding: Rs {float(order.balance):,.2f}.")
            if order.delivery_date:
                lines.append(f"Delivery date: {order.delivery_date.strftime('%d %b %Y')}.")
            return " ".join(lines), ["Record Payment", "Show order pipeline"]

        if context.supplier_id:
            supplier = db.query(Supplier).filter(Supplier.id == context.supplier_id).first()
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

        if context.material_id:
            material = db.query(Material).filter(Material.id == context.material_id).first()
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

        if context.client_id:
            client = db.query(Client).filter(Client.id == context.client_id).first()
            if not client:
                return None
            total_sales = sum((o.order_value for o in client.orders), 0)
            return (
                f"{client.name} ({client.client_code}): {len(client.orders)} orders, "
                f"Rs {float(total_sales):,.2f} in total order value.",
                [],
            )

        if context.employee_id:
            employee = db.query(Employee).filter(Employee.id == context.employee_id).first()
            if not employee:
                return None
            return (
                f"{employee.name} ({employee.employee_code}), {employee.department or 'no department'}. Status: {employee.status}.",
                [f"Show {employee.name.split()[0]}'s tasks"],
            )

        return None

    @staticmethod
    def _stock_summary(db: Session):
        materials = db.query(Material).all()
        total_value = sum(m.stock_value for m in materials)
        return (
            f"You have {len(materials)} materials tracked, worth Rs {total_value:,.2f} in current stock.",
            ["Check low stock", "Show pending orders"], [],
        )

    @staticmethod
    def _route_leave_query(m: str, db: Session, current_employee_id: Optional[int]):
        """"My leaves", "show Pankaj's leaves" - same real-data pattern as
        _route_task_query: "my" resolves through the actual
        User.employee_id link, a named person resolves through a live
        Employee.name query, never hard-coded. Works from any page,
        since it's checked unconditionally in _dispatch before any
        context-specific branch, not gated behind what record the user
        happened to be viewing when they opened the chat."""
        if "leave" not in m:
            return None

        is_mine = any(w in m for w in ["my leave", "my leaves"])
        if is_mine:
            if current_employee_id is None:
                return ("Your account isn't linked to an employee record, so I can't look up "
                        "your leave records. Ask a master/manager to link your account to your "
                        "employee profile."), [], []
            employee = db.query(Employee).filter(Employee.id == current_employee_id).first()
            return ChatService._leaves_for_employee(db, employee)

        name = ChatService._extract_employee_name_for_leaves(m)
        if name:
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
                        "your tasks. Ask a master/manager to link your account to your employee "
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
            tasks = [t for t in tasks if t.date.date() < today and t.status != "Completed"]
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
    def _low_stock(db: Session):
        materials = db.query(Material).all()
        low = [m for m in materials if m.current_stock <= m.minimum_stock]
        if not low:
            return "All materials are above minimum stock levels.", [], []
        records = [{
            "type": "Material", "label": m.name,
            "sublabel": f"{m.current_stock}/{m.minimum_stock} {m.unit}",
            "path": f"/materials/{m.id}",
        } for m in low[:10]]
        return f"{len(low)} materials at or below minimum stock.", [], records

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
