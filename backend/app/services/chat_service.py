from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.constants import MATERIAL_TYPES
from app.models.product import Product
from app.models.client import Client
from app.models.estimate import Estimate

import logging

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user") -> Tuple[str, List[str]]:
        message_lower = message.lower()

        if any(word in message_lower for word in ["low stock", "alert", "reorder"]):
            response, suggestions = ChatService._handle_low_stock_query(db)
        elif any(word in message_lower for word in ["inventory", "stock", "material", "quantity"]):
            response, suggestions = ChatService._handle_inventory_query(db)
        elif any(word in message_lower for word in ["estimate", "quote", "cost", "price"]):
            response, suggestions = ChatService._handle_estimate_query(db)
        elif any(word in message_lower for word in ["client", "customer"]):
            response, suggestions = ChatService._handle_client_query(db)
        elif any(word in message_lower for word in ["payment", "invoice", "finance", "revenue"]):
            if user_role == "master":
                response, suggestions = ChatService._handle_payment_query(db)
            else:
                response, suggestions = "You do not have permission to view financial information.", []
        elif "help" in message_lower:
            response, suggestions = ChatService._handle_help_query()
        else:
            response, suggestions = ChatService._handle_default_query(message)

        return response, suggestions

    @staticmethod
    def _handle_inventory_query(db: Session) -> Tuple[str, List[str]]:
        items = db.query(Product).all()
        total_items = len(items)
        total_quantity = sum(i.quantity or 0 for i in items)
        total_value = sum((i.quantity or 0) * (i.price_per_unit or 0) for i in items)

        response = f"Inventory Summary: {total_items} material types, {total_quantity} units, Rs {total_value:,.2f} total value"
        suggestions = ["View detailed stock", "Generate inventory report", "Check material prices"]
        return response, suggestions

    @staticmethod
    def _handle_low_stock_query(db: Session) -> Tuple[str, List[str]]:
        low_items = db.query(Product).filter(Product.quantity <= Product.min_quantity).all()

        if not low_items:
            return "All materials are above minimum stock levels. No alerts.", []

        response = "Low Stock Alert: {count} items below minimum.\n".format(count=len(low_items))
        for item in low_items[:10]:
            response += f"- {item.material_type} ({item.sku}): {item.quantity}/{item.min_quantity} units\n"
        return response, ["Reorder now", "View detailed alerts"]

    @staticmethod
    def _handle_estimate_query(db: Session) -> Tuple[str, List[str]]:
        estimates = db.query(Estimate).all()
        drafts = [e for e in estimates if e.status == "draft"]

        response = f"Estimates: {len(estimates)} total, {len(drafts)} drafts"
        if drafts:
            response += f"\nPending estimates value: Rs {sum(e.total_cost or 0 for e in drafts):,.2f}"

        return response, ["Create new estimate", "View pending", "Send to client"]

    @staticmethod
    def _handle_client_query(db: Session) -> Tuple[str, List[str]]:
        clients = db.query(Client).all()
        return f"Clients: {len(clients)} clients on file", ["View all clients", "Add new client"]

    @staticmethod
    def _handle_payment_query(db: Session) -> Tuple[str, List[str]]:
        return "Financial information available for master users only", ["View payment history", "Check pending payments"]

    @staticmethod
    def _handle_help_query() -> Tuple[str, List[str]]:
        return "I can help with inventory management, stock alerts, estimates, client info, and more. What do you need?", ["Check inventory", "See low stock items", "View estimates", "Browse features"]

    @staticmethod
    def _handle_default_query(message: str) -> Tuple[str, List[str]]:
        return f"I understand you asked about: '{message}'. Please specify inventory, estimates, clients, payments, or ask for help.", ["Ask for help", "Check inventory", "View dashboard"]
