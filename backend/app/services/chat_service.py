"""Rule-based business-intelligence assistant. Answers common questions by
querying the current domain directly - not a real LLM integration. The
OPENAI_API_KEY setting already exists in core/config.py for a future
upgrade to real natural-language understanding; this keyword-matching
version is a working, testable placeholder for that."""
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.client import Client
from app.models.order import Order
from app.models.payment import Payment
from app.models.employee import Employee


class ChatService:
    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user") -> Tuple[str, List[str]]:
        m = message.lower()

        if any(w in m for w in ["low stock", "reorder", "alert"]):
            return ChatService._low_stock(db)
        if any(w in m for w in ["stock", "material", "inventory"]):
            return ChatService._stock_summary(db)
        if any(w in m for w in ["order", "project", "pipeline"]):
            return ChatService._orders_summary(db)
        if any(w in m for w in ["client", "customer"]):
            return ChatService._clients_summary(db)
        if any(w in m for w in ["payment", "revenue", "pending amount", "balance"]):
            if user_role in ("master", "manager"):
                return ChatService._payments_summary(db)
            return "Financial information is available to master/manager accounts only.", []
        if any(w in m for w in ["employee", "staff", "attendance"]):
            return ChatService._staff_summary(db)
        if "help" in m:
            return (
                "I can answer questions about stock/materials, orders, clients, payments "
                "(master/manager only), and staff. Try asking about low stock, pending orders, "
                "or client count.",
                ["Check low stock", "Show pending orders", "How many clients?"],
            )
        return (
            f"I didn't quite catch that. Try asking about stock, orders, clients, payments, or staff.",
            ["Check low stock", "Show pending orders", "Show staff summary"],
        )

    @staticmethod
    def _stock_summary(db: Session):
        materials = db.query(Material).all()
        total_value = sum(m.stock_value for m in materials)
        return (
            f"You have {len(materials)} materials tracked, worth Rs {total_value:,.2f} in current stock.",
            ["Check low stock", "Show pending orders"],
        )

    @staticmethod
    def _low_stock(db: Session):
        materials = db.query(Material).all()
        low = [m for m in materials if m.current_stock <= m.minimum_stock]
        if not low:
            return "All materials are above minimum stock levels.", []
        lines = "\n".join(f"- {m.name}: {m.current_stock}/{m.minimum_stock} {m.unit}" for m in low[:10])
        return f"{len(low)} materials at or below minimum stock:\n{lines}", ["Export stock dashboard"]

    @staticmethod
    def _orders_summary(db: Session):
        orders = db.query(Order).all()
        active = [o for o in orders if o.project_status != "Completed"]
        return (
            f"{len(orders)} total orders, {len(active)} still active.",
            ["Show pending payments", "Show client count"],
        )

    @staticmethod
    def _clients_summary(db: Session):
        count = db.query(Client).count()
        return f"You have {count} clients on file.", ["Show pending orders"]

    @staticmethod
    def _payments_summary(db: Session):
        orders = db.query(Order).all()
        pending = sum(float(o.balance or 0) for o in orders)
        received = sum(float(o.total_received or 0) for o in orders)
        return (
            f"Total received across all orders: Rs {received:,.2f}. Pending payment: Rs {pending:,.2f}.",
            ["Export payments"],
        )

    @staticmethod
    def _staff_summary(db: Session):
        employees = db.query(Employee).filter(Employee.status == "Active").all()
        return f"{len(employees)} active employees on the team.", ["Show pending orders"]
