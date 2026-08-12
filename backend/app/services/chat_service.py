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
from app.schemas.chat import ChatContext, ProposedAction

THIS_RECORD_WORDS = ["this order", "this material", "this client", "this employee",
                      "summarize", "summarise", "should i reorder", "reorder this"]
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
                         context: Optional[ChatContext] = None
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

        text, suggestions, records = ChatService._dispatch(m, db, user_role, context)
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
    def _dispatch(m: str, db: Session, user_role: str, context: Optional[ChatContext]) -> Tuple[str, List[str], List[dict]]:
        if context and any(w in m for w in THIS_RECORD_WORDS):
            contextual = ChatService._answer_from_context(m, db, user_role, context)
            if contextual:
                text, suggestions = contextual
                return text, suggestions, []

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
                        ["Record Purchase"],
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
                ["Create Order", "Record Payment"],
            )

        if context.employee_id:
            employee = db.query(Employee).filter(Employee.id == context.employee_id).first()
            if not employee:
                return None
            return (
                f"{employee.name} ({employee.employee_code}), {employee.department or 'no department'}. Status: {employee.status}.",
                ["Assign Task", "Record Attendance"],
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
        return f"{len(low)} materials at or below minimum stock.", ["Export stock dashboard"], records

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
            ["Export payments"], records,
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
