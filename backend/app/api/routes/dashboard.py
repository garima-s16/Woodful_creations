from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.material import Material
from app.models.purchase import Purchase
from app.models.order import Order
from app.models.employee import Employee
from app.models.daily_task import DailyTask
from app.models.attendance import Attendance
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stock")
def stock_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    materials = db.query(Material).all()
    total_stock_value = sum(m.stock_value for m in materials)
    low_stock = [m for m in materials if m.current_stock <= m.minimum_stock and m.current_stock > 0]
    out_of_stock = [m for m in materials if m.current_stock <= 0]
    purchase_value = sum(float(p.invoice_total or 0) for p in db.query(Purchase).all())

    category_summary = defaultdict(lambda: {"items": 0, "stock_quantity": 0, "stock_value": 0.0})
    for m in materials:
        cs = category_summary[m.category or "Uncategorized"]
        cs["items"] += 1
        cs["stock_quantity"] += m.current_stock or 0
        cs["stock_value"] += m.stock_value

    return {
        "total_stock_value": round(total_stock_value, 2),
        "low_stock_items": len(low_stock),
        "out_of_stock_items": len(out_of_stock),
        "purchase_value": round(purchase_value, 2),
        "low_stock_action_list": [
            {
                "id": m.id, "material": m.name, "current": m.current_stock, "minimum": m.minimum_stock,
                "status": m.stock_status,
                "suggested_order": max(m.minimum_stock - m.current_stock, 0),
                "supplier": m.primary_supplier.name if m.primary_supplier else None,
            }
            for m in (low_stock + out_of_stock)
        ],
        "category_summary": [
            {"category": cat, **stats} for cat, stats in category_summary.items()
        ],
    }


@router.get("/orders")
def orders_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    orders = db.query(Order).all()
    active_statuses = {"Completed"}
    active_orders = [o for o in orders if o.project_status not in active_statuses]

    pipeline = defaultdict(int)
    for o in orders:
        pipeline[o.project_status] += 1

    return {
        "total_order_value": float(sum((o.order_value or Decimal("0")) for o in orders)),
        "total_received": float(sum((o.total_received or Decimal("0")) for o in orders)),
        "pending_payment": float(sum((o.balance or Decimal("0")) for o in orders)),
        "active_orders": len(active_orders),
        "order_pipeline": [{"status": s, "orders": c} for s, c in pipeline.items()],
        "top_orders": [
            {
                "id": o.id, "order_id": o.order_code, "client": o.client.name if o.client else None,
                "order_value": float(o.order_value or 0), "received": float(o.total_received or 0),
                "pending": float(o.balance or 0), "progress": o.progress_percent, "status": o.project_status,
            }
            for o in sorted(orders, key=lambda x: x.order_value or 0, reverse=True)
        ],
        "order_profitability": [OrderService.profitability(db, o) for o in orders],
    }


@router.get("/staff")
def staff_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    tasks = db.query(DailyTask).all()

    task_status_summary = defaultdict(int)
    for t in tasks:
        task_status_summary[t.status] += 1

    total_overtime = sum(a.overtime_hours for a in db.query(Attendance).all())

    performance = []
    for e in employees:
        emp_tasks = [t for t in tasks if t.employee_id == e.id]
        completed = [t for t in emp_tasks if t.status == "Completed"]
        emp_attendance = [a for a in e.attendance_records]
        hours = sum(a.working_hours for a in emp_attendance)
        overtime = sum(a.overtime_hours for a in emp_attendance)
        performance.append({
            "employee": e.name, "department": e.department,
            "tasks": len(emp_tasks), "completed": len(completed),
            "completion_percent": round(len(completed) / len(emp_tasks), 4) if emp_tasks else 0,
            "hours": round(hours, 2), "overtime": round(overtime, 2),
        })

    return {
        "active_employees": len(employees),
        "pending_tasks": task_status_summary.get("Not Started", 0) + task_status_summary.get("In Progress", 0),
        "completed_tasks": task_status_summary.get("Completed", 0),
        "total_overtime": round(total_overtime, 2),
        "task_status_summary": [{"status": s, "count": c} for s, c in task_status_summary.items()],
        "employee_performance": performance,
    }
