from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_token
from app.models.product import Product
from app.models.client_project import ClientProject
from app.models.payment import Payment
from app.models.employee import Employee
from app.models.attendance import Attendance
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/")
def get_dashboard(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    user_role = auth.get("role", "user")
    
    products = db.query(Product).all()
    low_stock_items = [p for p in products if p.quantity <= p.min_quantity]
    
    projects = db.query(ClientProject).all()
    pending_projects = [p for p in projects if p.delivery_status != "delivered"]
    
    payments = db.query(Payment).all()
    pending_payments = [p for p in payments if p.status == "pending"]
    
    stats = {
        "totalMaterials": len(products),
        "lowStockItems": len(low_stock_items),
        "totalInventoryValue": round(sum(p.price_per_unit * p.quantity for p in products), 2),
        "pendingEstimates": len(pending_projects),
        "activeClients": len(set([p.client_id for p in projects])),
        "pendingPayments": round(sum([p.amount for p in pending_payments]), 2),
    }
    
    if user_role == "master":
        completed_payments = [p for p in payments if p.status == "completed"]
        stats["totalRevenue"] = round(sum([p.amount for p in completed_payments]), 2)
        
        employees = db.query(Employee).filter(Employee.is_active == True).all()
        stats["totalEmployees"] = len(employees)
        
        today = datetime.now().date()
        today_attendance = db.query(Attendance).filter(
            Attendance.attendance_date >= datetime.combine(today, datetime.min.time())
        ).all()
        stats["presentToday"] = len([a for a in today_attendance if a.status == "present"])
    
    recent_activity = [
        {"id": 1, "type": "inventory", "message": "Inventory system initialized", "timestamp": str(datetime.now())},
        {"id": 2, "type": "system", "message": "Chat feature activated", "timestamp": str(datetime.now())},
        {"id": 3, "type": "system", "message": "Dashboard loaded successfully", "timestamp": str(datetime.now())}
    ]
    
    return {
        "stats": stats,
        "recentActivity": recent_activity,
        "userRole": user_role
    }