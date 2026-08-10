from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user as verify_auth
from app.models.attendance import Attendance
from app.models.client_project import ClientProject
from app.models.employee import Employee
from app.models.payment import Payment
from app.models.product import Product

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/")
def get_dashboard(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    user_role = auth.get("role", "user")

    products = db.query(Product).all()
    low_stock_items = [p for p in products if getattr(p, "quantity", 0) <= getattr(p, "min_quantity", getattr(p, "min_stock", 0))]

    projects = db.query(ClientProject).all()
    pending_projects = [p for p in projects if getattr(p, "delivery_status", "") != "delivered"]

    payments = db.query(Payment).all()
    pending_payments = [p for p in payments if getattr(p, "status", "") == "pending"]

    stats = {
        "totalMaterials": len(products),
        "lowStockItems": len(low_stock_items),
        "totalInventoryValue": round(sum(getattr(p, "price_per_unit", 0) * getattr(p, "quantity", 0) for p in products), 2),
        "pendingEstimates": len(pending_projects),
        "activeClients": len({p.client_id for p in projects if getattr(p, "client_id", None) is not None}),
        "pendingPayments": round(sum(getattr(p, "amount", 0) for p in pending_payments), 2),
    }

    if user_role == "master":
        completed_payments = [p for p in payments if getattr(p, "status", "") == "completed"]
        stats["totalRevenue"] = round(sum(getattr(p, "amount", 0) for p in completed_payments), 2)

        employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()
        stats["totalEmployees"] = len(employees)

        today = datetime.now().date()
        today_attendance = db.query(Attendance).filter(Attendance.attendance_date >= datetime.combine(today, datetime.min.time())).all()
        stats["presentToday"] = len([a for a in today_attendance if getattr(a, "status", "") == "present"])

    return {"stats": stats, "recentActivity": [], "userRole": user_role}
