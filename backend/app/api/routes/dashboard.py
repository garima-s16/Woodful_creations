from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.material import Material
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.models.order import Order
from app.models.employee import Employee
from app.models.daily_task import DailyTask
from app.models.production_job import ProductionJob
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

    recent_purchases = db.query(Purchase).order_by(Purchase.date.desc()).limit(10).all()
    recent_issues = db.query(Issue).order_by(Issue.date.desc()).limit(10).all()
    recent_stock_movement = sorted(
        [
            {
                "type": "IN", "date": p.date.isoformat() if p.date else None, "material": p.material.name if p.material else None,
                "quantity": float(p.quantity), "unit": p.unit, "reference": p.purchase_code,
                "detail": p.supplier.name if p.supplier else None,
            }
            for p in recent_purchases
        ] + [
            {
                "type": "OUT", "date": i.date.isoformat() if i.date else None, "material": i.material.name if i.material else None,
                "quantity": float(i.quantity_issued), "unit": i.unit, "reference": i.issue_code,
                "detail": i.order.order_code if i.order else i.issued_to,
            }
            for i in recent_issues
        ],
        key=lambda row: row["date"] or "", reverse=True,
    )[:10]

    category_summary = defaultdict(lambda: {"items": 0, "stock_quantity": 0, "stock_value": 0.0})
    for m in materials:
        cs = category_summary[m.category or "Uncategorized"]
        cs["items"] += 1
        cs["stock_quantity"] += m.current_stock or 0
        cs["stock_value"] += m.stock_value

    is_privileged = auth.get("role", "user") in ("master",)
    return {
        "total_stock_value": round(total_stock_value, 2) if is_privileged else None,
        "low_stock_items": len(low_stock),
        "out_of_stock_items": len(out_of_stock),
        "purchase_value": round(purchase_value, 2) if is_privileged else None,
        "recent_stock_movement": recent_stock_movement,
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
            {"category": cat, **{k: (v if is_privileged or k != "stock_value" else None) for k, v in stats.items()}}
            for cat, stats in category_summary.items()
        ],
    }


@router.get("/orders")
def orders_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    orders = db.query(Order).all()
    active_statuses = {"Completed"}
    active_orders = [o for o in orders if o.project_status not in active_statuses]

    pipeline = defaultdict(int)
    for o in orders:
        pipeline[o.project_status] += 1

    return {
        "total_order_value": float(sum((o.order_value or Decimal("0")) for o in orders)) if is_privileged else None,
        "total_received": float(sum((o.total_received or Decimal("0")) for o in orders)) if is_privileged else None,
        "pending_payment": float(sum((o.balance or Decimal("0")) for o in orders)) if is_privileged else None,
        "active_orders": len(active_orders),
        "order_pipeline": [{"status": s, "orders": c} for s, c in pipeline.items()],
        "top_orders": [
            {
                "id": o.id, "order_id": o.order_code, "client": o.client.name if o.client else None,
                "order_value": float(o.order_value or 0) if is_privileged else None,
                "received": float(o.total_received or 0) if is_privileged else None,
                "pending": float(o.balance or 0) if is_privileged else None,
                "progress": o.progress_percent, "status": o.project_status,
            }
            for o in sorted(orders, key=lambda x: x.order_value or 0, reverse=True)
        ],
        # Profitability is entirely financial - no partial/redacted view,
        # matching "profit, margin... must NOT be received" exactly.
        "order_profitability": [OrderService.profitability(db, o) for o in orders] if is_privileged else [],
    }


@router.get("/staff")
def staff_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    own_employee_id = auth.get("employee_id")
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    tasks = db.query(DailyTask).all()

    task_status_summary = defaultdict(int)
    for t in tasks:
        task_status_summary[t.status] += 1

    production_jobs = db.query(ProductionJob).all()
    production_status_summary = defaultdict(int)
    for p in production_jobs:
        production_status_summary[p.status] += 1

    total_overtime = sum(a.overtime_hours for a in db.query(Attendance).all())

    performance = []
    today = datetime.utcnow().date()
    for e in employees:
        emp_tasks = [t for t in tasks if t.employee_id == e.id]
        completed = [t for t in emp_tasks if t.status == "DONE"]
        overdue = [t for t in emp_tasks if t.date.date() < today and t.status != "DONE"]
        emp_attendance = [a for a in e.attendance_records]
        hours = sum(a.working_hours for a in emp_attendance)
        overtime = sum(a.overtime_hours for a in emp_attendance)
        performance.append({
            "employee_id": e.id, "employee": e.name, "department": e.department,
            "tasks": len(emp_tasks), "completed": len(completed), "overdue": len(overdue),
            "completion_percent": round(len(completed) / len(emp_tasks), 4) if emp_tasks else 0,
            "hours": round(hours, 2), "overtime": round(overtime, 2),
        })

    return {
        "active_employees": len(employees),
        "pending_tasks": task_status_summary.get("TO DO", 0) + task_status_summary.get("DOING", 0),
        "completed_tasks": task_status_summary.get("DONE", 0),
        "total_overtime": round(total_overtime, 2),
        "task_status_summary": [{"status": s, "count": c} for s, c in task_status_summary.items()],
        "production_status_summary": [{"status": s, "count": c} for s, c in production_status_summary.items()],
        "employee_performance": performance if is_privileged else [
            p for p in performance if p["employee_id"] == own_employee_id
        ],
    }
