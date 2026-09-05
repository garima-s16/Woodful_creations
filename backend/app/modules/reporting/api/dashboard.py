from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session, selectinload

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.modules.inventory.models import Material, Purchase
from app.modules.operations.models import Issue
from app.modules.sales.models import Order
from app.modules.hr.models import Employee, Attendance
from app.modules.operations.models import DailyTask
from app.modules.operations.models import ProductionJob
from app.modules.sales.order_service import OrderService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stock")
def stock_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)

    active_materials = db.query(Material).filter(Material.is_active.is_(True))

    total_stock_value = float(
        db.query(func.coalesce(func.sum(Material.stock_value), 0))
        .filter(Material.is_active.is_(True)).scalar() or 0
    )
    purchase_value = float(db.query(func.sum(Purchase.invoice_total)).scalar() or 0)

    low_stock_count = active_materials.filter(
        Material.current_stock <= Material.minimum_stock, Material.current_stock > 0,
    ).count()
    out_of_stock_count = active_materials.filter(Material.current_stock <= 0).count()

    # Only the bounded reorder-suggestion list actually needs full Material
    # rows (and their primary_supplier, eager-loaded here to avoid a
    # separate query per row) - counts/totals above never load a row at all.
    low_or_out_of_stock = (
        active_materials
        .filter(Material.current_stock <= Material.minimum_stock)
        .options(selectinload(Material.primary_supplier))
        .order_by(Material.current_stock.asc())
        .all()
    )

    recent_purchases = (
        db.query(Purchase).options(selectinload(Purchase.material), selectinload(Purchase.supplier))
        .order_by(Purchase.date.desc()).limit(10).all()
    )
    recent_issues = (
        db.query(Issue).options(selectinload(Issue.material), selectinload(Issue.order))
        .order_by(Issue.date.desc()).limit(10).all()
    )
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

    category_rows = (
        db.query(
            func.coalesce(Material.category, "Uncategorized").label("category"),
            func.count(Material.id).label("items"),
            func.coalesce(func.sum(Material.current_stock), 0).label("stock_quantity"),
            func.coalesce(func.sum(Material.stock_value), 0).label("stock_value"),
        )
        .filter(Material.is_active.is_(True))
        .group_by(func.coalesce(Material.category, "Uncategorized"))
        .all()
    )

    return {
        "total_stock_value": round(total_stock_value, 2) if is_privileged else None,
        "low_stock_items": low_stock_count,
        "out_of_stock_items": out_of_stock_count,
        "purchase_value": round(purchase_value, 2) if is_privileged else None,
        "recent_stock_movement": recent_stock_movement,
        "low_stock_action_list": [
            {
                "id": m.id, "material": m.name, "current": m.current_stock, "minimum": m.minimum_stock,
                "status": m.stock_status,
                "suggested_order": max(m.minimum_stock - m.current_stock, 0),
                "supplier": m.primary_supplier.name if m.primary_supplier else None,
            }
            for m in low_or_out_of_stock
        ],
        "category_summary": [
            {
                "category": row.category, "items": row.items,
                "stock_quantity": float(row.stock_quantity),
                "stock_value": round(float(row.stock_value), 2) if is_privileged else None,
            }
            for row in category_rows
        ],
    }


@router.get("/orders")
def orders_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)

    total_order_value = db.query(func.sum(Order.order_value)).scalar() or 0
    total_received = db.query(func.sum(Order.total_received)).scalar() or 0
    pending_payment = db.query(func.sum(Order.balance)).scalar() or 0
    active_orders = db.query(func.count(Order.id)).filter(Order.project_status != "Completed").scalar() or 0
    pipeline_rows = db.query(Order.project_status, func.count(Order.id)).group_by(Order.project_status).all()

    # "Top orders" is a bounded highlight list, not the full order
    # history - the previous version loaded and returned every order
    # ever placed, sorted in Python, which both got slower forever as
    # orders accumulated and triggered a separate query per order for
    # `.client.name` (N+1). Sorted/limited at the DB level instead,
    # with the client relationship eager-loaded in the same query.
    TOP_ORDERS_LIMIT = 10
    sort_column = Order.order_value if is_privileged else Order.progress_percent
    top_orders_query = (
        db.query(Order)
        .options(selectinload(Order.client))
        .order_by(sort_column.desc().nullslast())
        .limit(TOP_ORDERS_LIMIT)
    )
    top_orders = top_orders_query.all()

    return {
        "total_order_value": float(total_order_value) if is_privileged else None,
        "total_received": float(total_received) if is_privileged else None,
        "pending_payment": float(pending_payment) if is_privileged else None,
        "active_orders": active_orders,
        "order_pipeline": [{"status": s, "orders": c} for s, c in pipeline_rows],
        "top_orders": [
            {
                "id": o.id, "order_id": o.order_code, "client": o.client.name if o.client else None,
                "order_value": float(o.order_value or 0) if is_privileged else None,
                "received": float(o.total_received or 0) if is_privileged else None,
                "pending": float(o.balance or 0) if is_privileged else None,
                "progress": o.progress_percent, "status": o.project_status,
            }
            for o in top_orders
        ],
        # Profitability shown alongside the same bounded top-orders set,
        # not the full order history - matches "top orders" scope.
        # Profitability is entirely financial - no partial/redacted view,
        # matching "profit, margin... must NOT be received" exactly.
        "order_profitability": list(OrderService.profitability_bulk(db, top_orders).values()) if is_privileged else [],
        # True aggregate across every order, not derived from the
        # top-orders sample above - see overall_gross_margin's own
        # docstring for why those can't be the same calculation.
        "overall_gross_margin_ratio": OrderService.overall_gross_margin(db)["gross_margin_ratio"] if is_privileged else None,
    }


@router.get("/staff")
def staff_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    own_employee_id = auth.get("employee_id")
    employees = db.query(Employee).filter(Employee.status == "Active").all()

    # Task status counts: one GROUP BY instead of loading every DailyTask
    # ever created (grows forever) just to count in Python.
    task_status_summary = dict(
        db.query(DailyTask.status, func.count(DailyTask.id)).group_by(DailyTask.status).all()
    )

    production_status_summary = dict(
        db.query(ProductionJob.status, func.count(ProductionJob.id)).group_by(ProductionJob.status).all()
    )

    total_overtime = db.query(func.sum(Attendance.overtime_hours)).scalar() or 0

    # Per-employee task/attendance figures: two GROUP BY queries (fixed
    # cost regardless of employee count), not a query-per-employee
    # (N+1 on e.attendance_records) or a Python scan of every task per
    # employee (O(employees x tasks) - the previous version re-scanned
    # the full task list once per employee).
    today = datetime.utcnow().date()
    task_rows = (
        db.query(
            DailyTask.employee_id,
            func.count(DailyTask.id).label("total"),
            func.coalesce(func.sum(case((DailyTask.status == "DONE", 1), else_=0)), 0).label("completed"),
            func.coalesce(func.sum(case(
                ((DailyTask.date < today) & (DailyTask.status != "DONE"), 1), else_=0
            )), 0).label("overdue"),
        )
        .group_by(DailyTask.employee_id)
        .all()
    )
    tasks_by_employee = {r.employee_id: r for r in task_rows}

    attendance_rows = (
        db.query(
            Attendance.employee_id,
            func.coalesce(func.sum(Attendance.working_hours), 0).label("hours"),
            func.coalesce(func.sum(Attendance.overtime_hours), 0).label("overtime"),
        )
        .group_by(Attendance.employee_id)
        .all()
    )
    attendance_by_employee = {r.employee_id: r for r in attendance_rows}

    performance = []
    for e in employees:
        t = tasks_by_employee.get(e.id)
        a = attendance_by_employee.get(e.id)
        total_tasks = t.total if t else 0
        completed = t.completed if t else 0
        overdue = t.overdue if t else 0
        performance.append({
            "employee_id": e.id, "employee": e.name, "department": e.department,
            "tasks": total_tasks, "completed": completed, "overdue": overdue,
            "completion_percent": round(completed / total_tasks, 4) if total_tasks else 0,
            "hours": round(float(a.hours), 2) if a else 0, "overtime": round(float(a.overtime), 2) if a else 0,
        })

    return {
        "active_employees": len(employees),
        "pending_tasks": task_status_summary.get("TO DO", 0) + task_status_summary.get("DOING", 0),
        "completed_tasks": task_status_summary.get("DONE", 0),
        "total_overtime": round(float(total_overtime), 2) if is_privileged else None,
        "task_status_summary": [{"status": s, "count": c} for s, c in task_status_summary.items()],
        "production_status_summary": [{"status": s, "count": c} for s, c in production_status_summary.items()],
        "employee_performance": performance if is_privileged else [
            p for p in performance if p["employee_id"] == own_employee_id
        ],
    }
