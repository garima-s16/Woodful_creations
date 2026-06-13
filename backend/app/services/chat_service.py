from sqlalchemy.orm import Session
from typing import Tuple, List
from datetime import datetime, timedelta
from app.database import StockItem, Estimate, Alert, Client
from app.core.constants import MATERIAL_TYPES
import logging

logger = logging.getLogger(__name__)

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
        items = db.query(StockItem).all()
        total_items = len(items)
        total_quantity = sum(item.quantity for item in items)
        total_value = sum(item.unit_cost * item.quantity for item in items)
        
        response = f"Inventory Summary: {total_items} material types, {total_quantity} units, Rs {total_value:,.2f} total value"
        suggestions = ["View detailed stock", "Generate inventory report", "Check material prices"]
        
        return response, suggestions
    
    @staticmethod
    def _handle_low_stock_query(db: Session) -> Tuple[str, List[str]]:
        low_items = db.query(StockItem).filter(StockItem.quantity <= StockItem.min_stock).all()
        
        if not low_items:
            response = "All materials are above minimum stock levels. No alerts."
            suggestions = []
        else:
            response = f"Low Stock Alert: {len(low_items)} items below minimum.\n"
            for item in low_items:
                response += f"- {item.name}: {item.quantity}/{item.min_stock} units\n"
            suggestions = ["Reorder now", "View detailed alerts", "Generate PO"]
        
        return response, suggestions
    
    @staticmethod
    def _handle_estimate_query(db: Session) -> Tuple[str, List[str]]:
        estimates = db.query(Estimate).all()
        drafts = [e for e in estimates if e.status == "draft"]
        
        response = f"Estimates: {len(estimates)} total, {len(drafts)} drafts"
        if drafts:
            response += f"\nPending estimates value: Rs {sum(e.total_amount for e in drafts):,.2f}"
        
        suggestions = ["Create new estimate", "View pending", "Send to client"]
        return response, suggestions
    
    @staticmethod
    def _handle_client_query(db: Session) -> Tuple[str, List[str]]:
        clients = db.query(Client).filter(Client.is_active == True).all()
        response = f"Clients: {len(clients)} active clients"
        suggestions = ["View all clients", "Add new client", "View client details"]
        return response, suggestions
    
    @staticmethod
    def _handle_payment_query(db: Session) -> Tuple[str, List[str]]:
        response = "Financial information available for master users only"
        suggestions = ["View payment history", "Generate invoice", "Check pending payments"]
        return response, suggestions
    
    @staticmethod
    def _handle_help_query() -> Tuple[str, List[str]]:
        response = "I can help with: Inventory management, Stock alerts, Estimates, Client info, and more. What do you need?"
        suggestions = ["Check inventory", "See low stock items", "View estimates", "Browse features"]
        return response, suggestions
    
    @staticmethod
    def _handle_default_query(message: str) -> Tuple[str, List[str]]:
        response = f"I understand you asked about: '{message}'. Please specify: inventory, estimates, clients, payments, or ask for help."
        suggestions = ["Ask for help", "Check inventory", "View dashboard"]
        return response, suggestions