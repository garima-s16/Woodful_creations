"""Reporting domain API routes: dashboard, analytics, global
search, and business-decision queries. Combines the former
dashboard.py, analytics.py, search.py, and business_decisions.py."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session, selectinload
from app.platform.database import get_db
from app.platform.security import get_current_user
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Issue
from app.modules.sales.models import Order
from app.modules.hr.models import Employee, Attendance
from app.modules.operations.models import DailyTask
from app.modules.operations.models import ProductionJob
from app.modules.sales.services import OrderService
from app.modules.inventory.services import StockService
from sqlalchemy.orm import Session
from app.platform.security import get_current_user, require_role
from app.modules.reporting import services as svc
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.modules.clients.models import Client
from app.modules.sales.models import Order, Estimate
from app.modules.procurement.models import Supplier
from app.modules.hr.models import Employee
from fastapi import APIRouter, Depends, HTTPException
from app.modules.reporting.services import get_business_risks, get_risk_for_entity


# --- dashboard.py ---
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@dashboard_router.get("/at-risk-orders")
def at_risk_orders_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Which open orders currently have a real material shortage, and
    why - the business-impact framing section 17 asks a dashboard to
    provide, built on the shortage-intelligence calculation that
    already existed for a single order at a time (see
    StockService.calculate_order_material_requirements and its
    business-wide sibling calculate_at_risk_orders) but was never
    proactively surfaced anywhere before this. No financial figures
    here - quantities and dates only, so this is visible to every
    authenticated user, matching "EMPLOYEE/USER can view stock/
    material and client/order status" rather than the Master-only
    redaction the stock/orders dashboards apply to money figures."""
    at_risk = StockService.calculate_at_risk_orders(db)
    return {
        "at_risk_order_count": len(at_risk),
        "orders": at_risk,
    }


@dashboard_router.get("/stock")
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
        .limit(20)
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


@dashboard_router.get("/orders")
def orders_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)

    total_order_value = db.query(func.sum(Order.order_value)).scalar() or 0
    total_received = db.query(func.sum(Order.total_received)).scalar() or 0
    pending_payment = db.query(func.sum(Order.balance)).scalar() or 0
    active_order_ids = [
        r[0] for r in db.query(Order.id).filter(Order.project_status != "Completed").all()
    ]
    active_orders = len(active_order_ids)
    pipeline_rows = db.query(Order.project_status, func.count(Order.id)).group_by(Order.project_status).all()

    # Delivery risk summary (P0.50 section 23) - counts ONLY active
    # (not yet Completed) orders, since a completed order's historical
    # delivery timing is not an actionable "needs attention today"
    # signal. Reuses bulk_attention_flags exactly - the same
    # calculation the Orders List's sort=risk and attention_risk_level
    # already use, never a separately-derived count.
    risk_counts = {"CRITICAL": 0, "AT_RISK": 0, "WATCH": 0, "ON_TRACK": 0}
    if active_order_ids:
        flags = OrderService.bulk_attention_flags(db, active_order_ids)
        for flag in flags.values():
            risk_counts[flag["risk_level"]] = risk_counts.get(flag["risk_level"], 0) + 1

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
        "delivery_risk_summary": risk_counts,
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


@dashboard_router.get("/staff")
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

    # working_hours is a Python-only property (computed from in_time/
    # out_time - see the model's own comment on why it can't just be a
    # column), so it cannot be passed to func.sum() as a SQL
    # expression - that would raise at query-compile time, every
    # single call, which is exactly what was happening here before
    # this fix. overtime_hours (a real column) is aggregated in SQL
    # above and reused per-employee below; working_hours is summed in
    # Python instead, from one single fetch of the raw in_time/out_time
    # columns - still one query total, not a query per employee.
    hours_rows = db.query(Attendance.employee_id, Attendance.in_time, Attendance.out_time, Attendance.overtime_hours).all()
    attendance_by_employee: dict = {}
    for employee_id, in_time, out_time, overtime in hours_rows:
        bucket = attendance_by_employee.setdefault(employee_id, {"hours": 0.0, "overtime": 0.0})
        if in_time and out_time:
            bucket["hours"] += (out_time - in_time).total_seconds() / 3600
        bucket["overtime"] += float(overtime or 0)

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
            "hours": round(a["hours"], 2) if a else 0, "overtime": round(a["overtime"], 2) if a else 0,
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


@dashboard_router.get("/cash-flow-forecast")
def cash_flow_forecast_dashboard(weeks: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137 feature 12 - Forward Cash-Flow Forecast. See
    svc.cash_flow_forecast's own docstring for exactly how EXPECTED /
    ACTUAL / OVERDUE / FORECAST are distinguished. Master-only - this
    is entirely financial data."""
    weeks = max(1, min(weeks, 12))
    return svc.cash_flow_forecast(db, weeks=weeks)


@dashboard_router.get("/owner-briefing")
def owner_briefing_dashboard(period: str = "daily", db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """Family 137 feature 11 - Owner Daily/Weekly Business Briefing.
    See svc.owner_briefing's own docstring for the real, existing
    signals synthesized. Master-only - this briefing surfaces
    financial and HR detail throughout."""
    if period not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="period must be 'daily' or 'weekly'.")
    return svc.owner_briefing(db, period=period)


# --- analytics.py ---
"""Analytics & Reporting API.

Every endpoint here delegates its actual aggregation to
app.modules.reporting.services, which reuses the same authoritative
models/calculations every other module already uses (OrderService.
profitability, Order.balance, Material.stock_value, etc.) - this file
only handles which role can call which endpoint, and drives that
scoping into the service call BEFORE aggregation runs, not by hiding
fields afterward.

RBAC follows the exact same split already established elsewhere in the
app:
  - purchases, payments, expenses -> master-only at the route (matching
    purchases.py / payments.py / project_expenses.py's own require_role
    gates)
  - sales/revenue/outstanding, projects (profitability portion) ->
    master-only, matching /api/dashboard/orders and
    /api/orders/{id}/profitability
  - inventory, production, tasks, operations -> open to any
    authenticated role, with financial sub-fields (stock value, order
    profitability) nulled for non-master, matching the stock/staff
    dashboards
  - workforce -> open, but a non-master viewer only ever sees their own
    employee_performance row, matching /api/dashboard/staff
"""

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@analytics_router.get("/sales")
def sales_analytics(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.sales_revenue_outstanding(db, months=months)


@analytics_router.get("/inventory")
def inventory_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.inventory_analytics(db, is_privileged=is_privileged)


@analytics_router.get("/purchases")
def purchases_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.purchases_analytics(db, months=months)


@analytics_router.get("/production")
def production_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return svc.production_analytics(db)


@analytics_router.get("/projects")
def projects_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.projects_analytics(db, is_privileged=is_privileged)


@analytics_router.get("/tasks")
def tasks_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return svc.tasks_analytics(db)


@analytics_router.get("/payments")
def payments_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.payments_analytics(db, months=months)


@analytics_router.get("/expenses")
def expenses_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.expenses_analytics(db, months=months)


@analytics_router.get("/workforce")
def workforce_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    own_employee_id = auth.get("employee_id")
    return svc.workforce_analytics(db, is_privileged=is_privileged, own_employee_id=own_employee_id)


@analytics_router.get("/operations")
def operations_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.operations_analytics(db, is_privileged=is_privileged)


@analytics_router.get("/alerts")
def all_alerts(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Consolidated alert feed across every domain this viewer is
    authorized to see - each alert already carries its own
    `drill_down` key so the frontend can route straight to the
    underlying records, matching every other domain function above."""
    is_privileged = auth.get("role", "user") in ("master",)
    alerts = []
    for a in svc.inventory_analytics(db, is_privileged=is_privileged)["alerts"]:
        alerts.append({**a, "domain": "inventory"})
    for a in svc.production_analytics(db)["alerts"]:
        alerts.append({**a, "domain": "production"})
    for a in svc.tasks_analytics(db)["alerts"]:
        alerts.append({**a, "domain": "tasks"})
    for a in svc.projects_analytics(db, is_privileged=is_privileged)["alerts"]:
        alerts.append({**a, "domain": "projects"})
    if is_privileged:
        for a in svc.sales_revenue_outstanding(db)["alerts"]:
            alerts.append({**a, "domain": "sales"})
        for a in svc.purchases_analytics(db)["alerts"]:
            alerts.append({**a, "domain": "purchases"})
        for a in svc.expenses_analytics(db)["alerts"]:
            alerts.append({**a, "domain": "expenses"})
    own_employee_id = auth.get("employee_id")
    for a in svc.workforce_analytics(db, is_privileged=is_privileged, own_employee_id=own_employee_id)["alerts"]:
        alerts.append({**a, "domain": "workforce"})
    return {"alerts": alerts}


@analytics_router.get("/whats-changed")
def whats_changed(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Grounded 'what changed this month' summary for the AI assistant
    and the analytics page alike - built only from real month-over-month
    comparisons already computed in analytics_service, never fabricated."""
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.month_over_month_summary(db, is_privileged=is_privileged)


# --- search.py ---
search_router = APIRouter(prefix="/api/search", tags=["search"])


RESULTS_PER_TYPE = 5


@search_router.get("/", response_model=List[dict])
def global_search(q: Optional[str] = Query(None, min_length=1), db: Session = Depends(get_db),
                   auth=Depends(get_current_user)):
    """Searches across the entities named in the product brief - client
    name/phone, order reference, estimate reference, material, supplier,
    employee, task - matching against both the human-scannable sequential
    code (CL-001, MAT-011, ...) and the opaque 10-character business_id,
    since a user might paste either. Returns a single ranked list, each
    result tagged with its record type so the frontend can route to the
    right detail page. Every entity here is already visible to all
    authenticated roles, so this endpoint doesn't need its own extra RBAC
    beyond that - it deliberately excludes role-restricted data (payments,
    salary, candidates, interviews) rather than complicate that per-result."""
    if not q or not q.strip():
        return []
    like = f"%{q.strip()}%"
    results = []

    for c in db.query(Client).filter(
        (Client.name.ilike(like)) | (Client.phone.ilike(like)) |
        (Client.client_code.ilike(like)) | (Client.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Client", "id": c.id, "label": c.name, "sublabel": c.client_code, "path": f"/clients/{c.id}"})

    for o in db.query(Order).filter(
        (Order.order_code.ilike(like)) | (Order.project_type.ilike(like)) | (Order.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Order", "id": o.id, "label": o.order_code,
                         "sublabel": o.project_type or (o.client.name if o.client else ""), "path": f"/orders/{o.id}"})

    for e in db.query(Estimate).filter(
        (Estimate.estimate_code.ilike(like)) | (Estimate.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Estimate", "id": e.id, "label": e.estimate_code,
                         "sublabel": e.client.name if e.client else "", "path": f"/estimates/{e.id}"})

    for m in db.query(Material).filter(
        (Material.name.ilike(like)) | (Material.material_code.ilike(like)) | (Material.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Material", "id": m.id, "label": m.name, "sublabel": m.material_code, "path": f"/materials/{m.id}"})

    for s in db.query(Supplier).filter(
        (Supplier.name.ilike(like)) | (Supplier.supplier_code.ilike(like)) | (Supplier.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Supplier", "id": s.id, "label": s.name, "sublabel": s.supplier_code, "path": f"/suppliers/{s.id}"})

    for emp in db.query(Employee).filter(
        (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like)) | (Employee.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Employee", "id": emp.id, "label": emp.name,
                         "sublabel": emp.department or emp.employee_code, "path": f"/employees/{emp.id}"})

    for t in db.query(DailyTask).filter(
        (DailyTask.task_description.ilike(like)) | (DailyTask.task_code.ilike(like)) | (DailyTask.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Task", "id": t.id, "label": t.task_description,
                         "sublabel": t.task_code, "path": f"/daily-tasks/{t.id}"})

    return results


# --- business_decisions.py ---
"""Family P0.49 (Cross-Module Business Risk) + P0.51 (Business
Decision Centre) API. Given its own business_decisions_router/prefix rather than folded
into dashboard.py's widget list, so a developer searching for
"business risk" or "business decision" finds this file directly
(section 4's discoverability requirement) - the underlying
calculation still lives in business_risk_service.py, reusing
OrderService.compute_order_health and SalarySlip data rather than
recalculating anything."""

business_decisions_router = APIRouter(prefix="/api/business-decisions", tags=["business-decisions"])


@business_decisions_router.get("/")
def list_business_decisions(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The P0.51 Business Decision Centre's single data source: a
    prioritized list of cross-module business risks plus a summary
    count. Financial/payroll risk items are only included for MASTER
    (sections 17/18/21) - an employee genuinely receives a shorter
    list, not a redacted copy of the same one."""
    is_privileged = auth.get("role", "user") in ("master",)
    return get_business_risks(db, is_privileged)


@business_decisions_router.get("/{entity_type}/{entity_id}")
def get_business_decision_for_entity(entity_type: str, entity_id: int,
                                      db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Section 19's AI contract - "why is this order at risk" needs one
    structured item, not the full list. Returns 404 both when the
    entity has no current risk and when the caller isn't authorized to
    see it (a non-privileged caller asking about a salary slip gets
    the same 404 as asking about one that doesn't exist - never a
    distinguishable "exists but you can't see it" leak)."""
    is_privileged = auth.get("role", "user") in ("master",)
    if entity_type not in ("order", "salary_slip", "salary_advance"):
        raise HTTPException(status_code=404, detail="No business decision found for this entity")
    result = get_risk_for_entity(db, entity_type, entity_id, is_privileged)
    if not result:
        raise HTTPException(status_code=404, detail="No business decision found for this entity")
    return result
