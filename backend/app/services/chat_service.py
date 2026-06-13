from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.client_project import ClientProject
from app.models.payment import Payment
from app.models.estimate import Estimate
from app.models.employee import Employee
from app.models.attendance import Attendance
from datetime import datetime, timedelta

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
    "Flexi Plywood": [6, 8]
}

class ChatService:
    
    @staticmethod
    def get_inventory_summary(db: Session) -> dict:
        products = db.query(Product).all()
        low_stock_items = [p for p in products if p.quantity <= p.min_quantity]
        total_value = sum(p.price_per_unit * p.quantity for p in products)
        
        return {
            "total_products": len(products),
            "low_stock_count": len(low_stock_items),
            "low_stock_items": [{
                "material": p.material_type,
                "thickness": p.thickness,
                "current": p.quantity,
                "minimum": p.min_quantity
            } for p in low_stock_items],
            "total_inventory_value": round(total_value, 2)
        }
    
    @staticmethod
    def get_client_summary(db: Session) -> dict:
        client_projects = db.query(ClientProject).all()
        pending_projects = [p for p in client_projects if p.delivery_status != "delivered"]
        total_pending_amount = sum([p.amount_pending for p in client_projects])
        
        return {
            "active_projects": len(client_projects),
            "pending_delivery": len(pending_projects),
            "total_pending_amount": round(total_pending_amount, 2)
        }
    
    @staticmethod
    def get_payment_summary(db: Session) -> dict:
        payments = db.query(Payment).all()
        pending_payments = [p for p in payments if p.status == "pending"]
        total_revenue = sum([p.amount for p in payments if p.status == "completed"])
        total_pending = sum([p.amount for p in pending_payments])
        
        return {
            "total_revenue": round(total_revenue, 2),
            "pending_payments": len(pending_payments),
            "total_pending_amount": round(total_pending, 2)
        }
    
    @staticmethod
    def get_attendance_summary(db: Session) -> dict:
        today = datetime.now().date()
        today_attendance = db.query(Attendance).filter(
            Attendance.attendance_date >= datetime.combine(today, datetime.min.time())
        ).all()
        
        present_count = len([a for a in today_attendance if a.status == "present"])
        absent_count = len([a for a in today_attendance if a.status == "absent"])
        
        return {
            "total_present": present_count,
            "total_absent": absent_count
        }
    
    @staticmethod
    def process_chat_message(message: str, db: Session, user_role: str = "user") -> tuple:
        message_lower = message.lower()
        suggestions = []
        
        if "inventory" in message_lower or "stock" in message_lower or "material" in message_lower:
            inventory_summary = ChatService.get_inventory_summary(db)
            response = f"Inventory Status: You have {inventory_summary['total_products']} material types in stock."
            
            if inventory_summary['low_stock_items']:
                low_items_str = "; ".join([
                    f"{item['material']} ({item['thickness']}mm) - Current: {item['current']}, Minimum: {item['minimum']}"
                    for item in inventory_summary['low_stock_items']
                ])
                response += f" LOW STOCK ALERT: {low_items_str}"
            
            response += f" Total inventory value: Rs {inventory_summary['total_inventory_value']:,.2f}"
            suggestions = [
                "View detailed inventory report",
                "Create reorder for low stock items",
                "Export inventory to Excel"
            ]
        
        elif "low stock" in message_lower or "alert" in message_lower or "reorder" in message_lower:
            inventory_summary = ChatService.get_inventory_summary(db)
            if inventory_summary["low_stock_items"]:
                items_list = "\n".join([
                    f"- {item['material']} ({item['thickness']}mm): {item['current']} / {item['minimum']} units"
                    for item in inventory_summary['low_stock_items']
                ])
                response = f"Low Stock Items:\n{items_list}\nRecommended Action: Place reorder immediately"
                suggestions = ["Auto-generate purchase order", "Contact suppliers", "Mark as ordered"]
            else:
                response = "No low stock alerts. All materials are above minimum quantity."
        
        elif "estimate" in message_lower or "quote" in message_lower or "cost" in message_lower:
            estimates = db.query(Estimate).all()
            pending_estimates = [e for e in estimates if e.status == "draft"]
            response = f"You have {len(pending_estimates)} pending estimates (draft) and {len(estimates) - len(pending_estimates)} completed estimates."
            if pending_estimates:
                response += f" Total pending estimate value: Rs {sum([e.total_cost for e in pending_estimates]):,.2f}"
            suggestions = ["Create new estimate", "View pending estimates", "Generate PDF estimate"]
        
        elif "client" in message_lower or "project" in message_lower:
            client_summary = ChatService.get_client_summary(db)
            response = f"Client Management: {client_summary['active_projects']} active projects. "
            response += f"{client_summary['pending_delivery']} projects pending delivery. "
            response += f"Total pending amount: Rs {client_summary['total_pending_amount']:,.2f}"
            suggestions = ["View all clients", "Check project status", "Send payment reminder"]
        
        elif "payment" in message_lower or "revenue" in message_lower or "finance" in message_lower:
            if user_role == "master":
                payment_summary = ChatService.get_payment_summary(db)
                response = f"Financial Summary: Total Revenue: Rs {payment_summary['total_revenue']:,.2f}. "
                response += f"Pending Payments: {payment_summary['pending_payments']} transactions totaling Rs {payment_summary['total_pending_amount']:,.2f}"
                suggestions = ["View payment report", "Send payment reminder", "Record payment"]
            else:
                response = "You do not have permission to view financial information."
        
        elif "employee" in message_lower or "attendance" in message_lower or "salary" in message_lower:
            if user_role == "master":
                attendance_summary = ChatService.get_attendance_summary(db)
                response = f"Today's Attendance: {attendance_summary['total_present']} present, {attendance_summary['total_absent']} absent."
                suggestions = ["View attendance details", "Generate salary slips", "View employee list"]
            else:
                response = "You do not have permission to view employee information."
        
        elif "help" in message_lower or "assist" in message_lower:
            response = "I can help you with: Inventory management, Stock alerts, Cost estimates, Client projects, "
            response += "Financial tracking, Attendance records, and Business analytics. What would you like to know?"
            suggestions = ["Show inventory", "Check pending tasks", "View dashboard"]
        
        elif "dashboard" in message_lower or "analytics" in message_lower or "report" in message_lower:
            inventory_summary = ChatService.get_inventory_summary(db)
            client_summary = ChatService.get_client_summary(db)
            payment_summary = ChatService.get_payment_summary(db) if user_role == "master" else {"total_revenue": 0}
            
            response = f"Dashboard Summary:\n"
            response += f"- Materials in Stock: {inventory_summary['total_products']}\n"
            response += f"- Low Stock Items: {inventory_summary['low_stock_count']}\n"
            response += f"- Active Projects: {client_summary['active_projects']}\n"
            response += f"- Pending Delivery: {client_summary['pending_delivery']}\n"
            if user_role == "master":
                response += f"- Total Revenue: Rs {payment_summary['total_revenue']:,.2f}\n"
            response += f"- Pending Amount: Rs {client_summary['total_pending_amount']:,.2f}"
            suggestions = ["Generate full report", "Export to Excel", "View detailed analytics"]
        
        else:
            response = f"I understand you're asking about '{message}'. I can assist with inventory management, "
            response += "cost estimation, client projects, attendance, payments, and business analytics. "
            response += "Please specify what you need help with."
            suggestions = ["View help options", "Browse features", "Contact support"]
        
        return response, suggestions