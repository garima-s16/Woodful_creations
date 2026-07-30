from sqlalchemy.orm import Session
from typing import Tuple, List
from app.models.product import Product
from app.models.estimate import Estimate
from app.models.client import Client
import logging

logger = logging.getLogger(__name__)

MATERIAL_TYPES = {
    "Plywood (Commercial/MR)": [6, 12, 18],
    "BWP/BWR Plywood": [6, 12, 18],
    "Marine Plywood": [6, 12, 18],
    "MDF": [3, 6, 12, 18],
    "Pre-Laminated MDF": [6, 12, 18],
    "HDHMR": [6, 12, 18],
    "HDF": [2.5, 3, 4],
    "Particle Board": [12, 18],
    "Pre-Laminated Particle Board": [18],
    "Block Board": [19, 25],
    "Flush Door Board": [30, 35],
    "WPC Board": [6, 12, 18],
    "PVC Board": [6, 12, 18],
    "Acrylic Sheet": [3, 5, 8],
    "Veneer MDF/Plywood": [6, 12, 18],
    "Flexi Plywood": [6, 8],
}


class ChatService:
    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user") -> Tuple[str, List[str]]:
        message_lower = message.lower()
        suggestions = []

        if any(word in message_lower for word in ["inventory", "stock", "material", "quantity"]):
            response, suggestions = ChatService._handle_inventory_query(db, message)

        elif any(word in message_lower for word in ["low stock", "alert", "reorder"]):
            response, suggestions = ChatService._handle_low_stock_query(db)

        elif any(word in message_lower for word in ["estimate", "quote", "cost", "price"]):
            response, suggestions = ChatService._handle_estimate_query(db)

        elif any(word in message_lower for word in ["client", "customer"]):
            response, suggestions = ChatService._handle_client_query(db)

        elif any(word in message_lower for word in ["payment", "invoice", "finance", "revenue"]):
            if user_role == "master":
                response, suggestions = ChatService._handle_payment_query(db)
            else:
                response = "You do not have permission to view financial information."
                suggestions = []

        elif "help" in message_lower:
            response, suggestions = ChatService._handle_help_query()

        else:
            response, suggestions = ChatService._handle_default_query(message)

        return response, suggestions

    @staticmethod
    def _handle_inventory_query(db: Session, message: str) -> Tuple[str, List[str]]:
        items = db.query(Product).filter(Product.is_active.is_(True)).all()
        total_items = len(items)
        total_quantity = sum(item.quantity for item in items)
        total_value = sum(item.price_per_unit * item.quantity for item in items)

        response = (
            f"Inventory Summary: {total_items} material types, "
            f"{total_quantity} units, Rs {total_value:,.2f} total value"
        )
        suggestions = ["View detailed stock", "Generate inventory report", "Check material prices"]
        return response, suggestions

    @staticmethod
    def _handle_low_stock_query(db: Session) -> Tuple[str, List[str]]:
        low_items = db.query(Product).filter(
            Product.quantity <= Product.min_quantity,
            Product.is_active.is_(True)
        ).all()

        if not low_items:
            response = "All materials are above minimum stock levels. No alerts."
            suggestions = []
        else:
            response = f"Low Stock: {len(low_items)} items below minimum.\n"
            for item in low_items:
                response += f"- {item.material_type}: {item.quantity}/{item.min_quantity} units\n"
            suggestions = ["Reorder now", "View detailed alerts", "Generate PO"]

        return response, suggestions

    @staticmethod
    def _handle_estimate_query(db: Session) -> Tuple[str, List[str]]:
        estimates = db.query(Estimate).all()
        drafts = [e for e in estimates if e.status == "draft"]

        response = f"Estimates: {len(estimates)} total, {len(drafts)} drafts"
        if drafts:
            response += f"\nPending estimates value: Rs {sum(e.total_cost for e in drafts):,.2f}"

        suggestions = ["Create new estimate", "View pending", "Send to client"]
        return response, suggestions

    @staticmethod
    def _handle_client_query(db: Session) -> Tuple[str, List[str]]:
        clients = db.query(Client).filter(Client.is_active.is_(True)).all()
        response = f"Clients: {len(clients)} active clients"
        suggestions = ["View all clients", "Add new client", "View client details"]
        return response, suggestions

    @staticmethod
    def _handle_payment_query(db: Session) -> Tuple[str, List[str]]:
        response = "Financial information is available for master users."
        suggestions = ["View payment history", "Generate invoice", "Check pending payments"]
        return response, suggestions

    @staticmethod
    def _handle_help_query() -> Tuple[str, List[str]]:
        response = (
            "I can help with: inventory management, stock alerts, "
            "estimates, client info, and more. What do you need?"
        )
        suggestions = ["Check inventory", "See low stock items", "View estimates", "Browse features"]
        return response, suggestions

    @staticmethod
    def _handle_default_query(message: str) -> Tuple[str, List[str]]:
        response = (
            f"You asked about: '{message}'. "
            "Please specify: inventory, estimates, clients, payments, or ask for help."
        )
        suggestions = ["Ask for help", "Check inventory", "View dashboard"]
        return response, suggestions
