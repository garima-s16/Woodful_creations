"""Family 12 - Analytics & Reporting.

This service ONLY aggregates data that already exists via the same
authoritative models/services every other module reads (Order,
OrderService.profitability, Material.stock_value, Payment, Purchase,
ProjectExpense, ProductionJob, DailyTask, Attendance, Employee). It
never invents a competing formula for something another module already
calculates - e.g. "outstanding" is always sum(Order.balance), the same
column OrderService keeps in sync on every payment; "stock value" is
always Material.stock_value, the same property the stock dashboard and
stock Excel export use.

Authorization is applied by the CALLER (routes/analytics.py) before
these functions run, by choosing which of these to call and whether to
pass is_privileged=True. Every function that returns money also takes
an is_privileged flag and nulls financial figures itself, so a
mistake in the route layer (forgetting to redact only in the response)
can't leak - the service is the second line of defense, not the only
one.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.models.order import Order
from app.models.payment import Payment
from app.models.purchase import Purchase
from app.models.material import Material
from app.models.project_expense import ProjectExpense
from app.models.production_job import ProductionJob
from app.models.daily_task import DailyTask
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.client import Client
from app.models.supplier import Supplier
from app.models.issue import Issue
from app.services.order_service import OrderService


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m") if dt else "Unknown"


def _last_n_months(n: int):
    """Chronological list of the last n calendar month keys, current month last."""
    today = datetime.utcnow().replace(day=1)
    months = []
    for i in range(n - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append(f"{year:04d}-{month:02d}")
    return months


# --------------------------------------------------------------------- #
# Sales / Revenue / Outstanding - master-only (financial). Built from
# Order + Payment, the same rows the Orders module and Payment Register
# already use; no parallel revenue formula.
# --------------------------------------------------------------------- #
def sales_revenue_outstanding(db: Session, months: int = 6) -> dict:
    orders = db.query(Order).options(selectinload(Order.client)).all()
    payments = db.query(Payment).options(selectinload(Payment.order)).order_by(Payment.date).all()

    total_order_value = sum((o.order_value or Decimal("0")) for o in orders)
    total_received = sum((o.total_received or Decimal("0")) for o in orders)
    total_outstanding = sum((o.balance or Decimal("0")) for o in orders)

    month_keys = _last_n_months(months)
    sales_trend = defaultdict(Decimal)   # orders booked, by order_date
    revenue_trend = defaultdict(Decimal)  # payments actually received, by payment date
    for o in orders:
        if o.order_date:
            sales_trend[_month_key(o.order_date)] += (o.order_value or Decimal("0"))
    for p in payments:
        if p.date:
            revenue_trend[_month_key(p.date)] += (p.amount or Decimal("0"))

    # Comparison: this month vs last month, on actual received revenue -
    # the only one of the two trends that represents cash actually in hand.
    this_month, last_month = month_keys[-1], month_keys[-2] if len(month_keys) > 1 else month_keys[-1]
    this_month_revenue = float(revenue_trend.get(this_month, 0))
    last_month_revenue = float(revenue_trend.get(last_month, 0))
    revenue_change_percent = (
        round(((this_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
        if last_month_revenue else None
    )

    # Outstanding drill-down: the actual orders/payments creating the
    # balance, not a fabricated list - straight from Order.balance.
    outstanding_orders = sorted(
        [o for o in orders if (o.balance or 0) > 0],
        key=lambda o: o.balance or 0, reverse=True,
    )
    outstanding_by_client = defaultdict(Decimal)
    for o in outstanding_orders:
        outstanding_by_client[o.client.name if o.client else "Unknown"] += (o.balance or Decimal("0"))

    # Aging (from order_date, since Order has no due date - same
    # approximation list_orders' overdue_only filter already uses).
    now = datetime.utcnow()
    aging_buckets = {"0-30 days": Decimal("0"), "31-60 days": Decimal("0"), "61-90 days": Decimal("0"), "90+ days": Decimal("0")}
    for o in outstanding_orders:
        age_days = (now - o.order_date).days if o.order_date else 0
        bucket = "0-30 days" if age_days <= 30 else "31-60 days" if age_days <= 60 else "61-90 days" if age_days <= 90 else "90+ days"
        aging_buckets[bucket] += (o.balance or Decimal("0"))

    # Payment mode mix, straight from the Payment Register.
    by_mode = defaultdict(Decimal)
    for p in payments:
        by_mode[p.payment_mode] += (p.amount or Decimal("0"))

    return {
        "total_order_value": float(total_order_value),
        "total_received": float(total_received),
        "total_outstanding": float(total_outstanding),
        "sales_trend": [{"month": m, "value": float(sales_trend.get(m, 0))} for m in month_keys],
        "revenue_trend": [{"month": m, "value": float(revenue_trend.get(m, 0))} for m in month_keys],
        "revenue_change_percent": revenue_change_percent,
        "payment_mode_breakdown": [{"mode": k, "amount": float(v)} for k, v in sorted(by_mode.items())],
        "aging_buckets": [{"bucket": k, "amount": float(v)} for k, v in aging_buckets.items()],
        "outstanding_by_client": [
            {"client": k, "amount": float(v)} for k, v in
            sorted(outstanding_by_client.items(), key=lambda x: x[1], reverse=True)[:10]
        ],
        # Real drill-down records: the orders that make up the outstanding total.
        "outstanding_orders": [{
            "id": o.id, "order_id": o.order_code, "client": o.client.name if o.client else None,
            "order_value": float(o.order_value or 0), "balance": float(o.balance or 0),
            "order_date": o.order_date.isoformat() if o.order_date else None, "status": o.project_status,
        } for o in outstanding_orders[:25]],
        "alerts": _sales_alerts(outstanding_orders, revenue_change_percent),
    }


def _sales_alerts(outstanding_orders, revenue_change_percent):
    alerts = []
    overdue_60 = [o for o in outstanding_orders if o.order_date and (datetime.utcnow() - o.order_date).days > 60]
    if overdue_60:
        total = sum(float(o.balance or 0) for o in overdue_60)
        alerts.append({
            "severity": "critical", "message": f"{len(overdue_60)} order(s) with payment outstanding over 60 days, totaling Rs {total:,.2f}.",
            "drill_down": "outstanding_orders",
        })
    if revenue_change_percent is not None and revenue_change_percent <= -20:
        alerts.append({
            "severity": "warning", "message": f"Revenue received this month is down {abs(revenue_change_percent):.1f}% versus last month.",
            "drill_down": "revenue_trend",
        })
    return alerts


# --------------------------------------------------------------------- #
# Inventory - open to all roles, but stock VALUE (a financial figure,
# quantity * average_rate) is master-only, matching the existing stock
# dashboard/export redaction exactly.
# --------------------------------------------------------------------- #
def inventory_analytics(db: Session, is_privileged: bool) -> dict:
    materials = db.query(Material).options(selectinload(Material.primary_supplier)).all()
    low_stock = [m for m in materials if 0 < (m.current_stock or 0) <= (m.minimum_stock or 0)]
    out_of_stock = [m for m in materials if (m.current_stock or 0) <= 0]

    category_value = defaultdict(lambda: {"items": 0, "stock_quantity": 0.0, "stock_value": 0.0})
    for m in materials:
        cs = category_value[m.category or "Uncategorized"]
        cs["items"] += 1
        cs["stock_quantity"] += float(m.current_stock or 0)
        cs["stock_value"] += m.stock_value

    result = {
        "total_materials": len(materials),
        "low_stock_count": len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "category_breakdown": [
            {"category": k, "items": v["items"], "stock_quantity": v["stock_quantity"],
             "stock_value": (v["stock_value"] if is_privileged else None)}
            for k, v in category_value.items()
        ],
        # Real drill-down: the actual materials behind "low stock", not a fabricated list.
        "low_stock_materials": [{
            "id": m.id, "material": m.name, "current_stock": float(m.current_stock or 0),
            "minimum_stock": float(m.minimum_stock or 0), "unit": m.unit,
            "suggested_order": max(float(m.minimum_stock or 0) - float(m.current_stock or 0), 0),
            "supplier": m.primary_supplier.name if m.primary_supplier else None,
        } for m in (low_stock + out_of_stock)],
        "total_stock_value": round(sum(m.stock_value for m in materials), 2) if is_privileged else None,
        "alerts": [],
    }
    if out_of_stock:
        result["alerts"].append({
            "severity": "critical",
            "message": f"{len(out_of_stock)} material(s) are out of stock.",
            "drill_down": "low_stock_materials",
        })
    elif low_stock:
        result["alerts"].append({
            "severity": "warning",
            "message": f"{len(low_stock)} material(s) are at or below their minimum stock level.",
            "drill_down": "low_stock_materials",
        })
    return result


# --------------------------------------------------------------------- #
# Purchases - master-only, matching purchases.py's own require_role gate.
# --------------------------------------------------------------------- #
def purchases_analytics(db: Session, months: int = 6) -> dict:
    purchases = db.query(Purchase).options(
        selectinload(Purchase.supplier), selectinload(Purchase.material)
    ).all()
    total_purchase_value = sum(float(p.invoice_total or 0) for p in purchases)
    pending_payment = [p for p in purchases if p.payment_status != "Paid"]

    month_keys = _last_n_months(months)
    trend = defaultdict(float)
    for p in purchases:
        if p.date:
            trend[_month_key(p.date)] += float(p.invoice_total or 0)

    by_supplier = defaultdict(float)
    for p in purchases:
        by_supplier[p.supplier.name if p.supplier else "Unknown"] += float(p.invoice_total or 0)

    return {
        "total_purchase_value": total_purchase_value,
        "pending_payment_count": len(pending_payment),
        "pending_payment_value": sum(float(p.invoice_total or 0) for p in pending_payment),
        "purchase_trend": [{"month": m, "value": trend.get(m, 0)} for m in month_keys],
        "top_suppliers_by_spend": [
            {"supplier": k, "amount": v} for k, v in
            sorted(by_supplier.items(), key=lambda x: x[1], reverse=True)[:10]
        ],
        # Drill-down: the actual purchases pending payment.
        "pending_purchases": [{
            "id": p.id, "purchase_id": p.purchase_code, "supplier": p.supplier.name if p.supplier else None,
            "material": p.material.name if p.material else None, "invoice_total": float(p.invoice_total or 0),
            "payment_status": p.payment_status, "date": p.date.isoformat() if p.date else None,
        } for p in pending_payment[:25]],
        "alerts": (
            [{"severity": "warning", "message": f"{len(pending_payment)} purchase(s) pending payment to suppliers.",
              "drill_down": "pending_purchases"}] if pending_payment else []
        ),
    }


# --------------------------------------------------------------------- #
# Production - open to all roles (ProductionJob has no financial fields).
# --------------------------------------------------------------------- #
def production_analytics(db: Session) -> dict:
    jobs = db.query(ProductionJob).options(
        selectinload(ProductionJob.employee), selectinload(ProductionJob.order)
    ).all()
    status_summary = defaultdict(int)
    for j in jobs:
        status_summary[j.status] += 1

    blocked = [j for j in jobs if j.status == "Blocked"]
    now = datetime.utcnow()
    open_7_plus = [
        j for j in jobs
        if j.status not in ("Completed",) and j.date and (now - j.date).days >= 7
    ]

    by_stage = defaultdict(lambda: {"planned": 0, "completed": 0})
    for j in jobs:
        s = by_stage[j.stage or "Unspecified"]
        s["planned"] += j.planned_qty or 0
        s["completed"] += j.completed_qty or 0

    return {
        "total_jobs": len(jobs),
        "status_summary": [{"status": s, "count": c} for s, c in status_summary.items()],
        "stage_throughput": [
            {"stage": k, "planned_qty": v["planned"], "completed_qty": v["completed"]}
            for k, v in by_stage.items()
        ],
        "blocked_count": len(blocked),
        "open_7_plus_days_count": len(open_7_plus),
        "blocked_jobs": [{
            "id": j.id, "job_id": j.job_code, "operation": j.operation, "order": j.order.order_code if j.order else None,
            "blocker_reason": j.blocker_reason, "date": j.date.isoformat() if j.date else None,
        } for j in blocked],
        "delayed_jobs": [{
            "id": j.id, "job_id": j.job_code, "operation": j.operation, "status": j.status,
            "order": j.order.order_code if j.order else None,
            "days_open": (now - j.date).days if j.date else None,
        } for j in open_7_plus[:25]],
        "alerts": (
            ([{"severity": "critical", "message": f"{len(blocked)} production job(s) are blocked.",
               "drill_down": "blocked_jobs"}] if blocked else [])
            + ([{"severity": "warning", "message": f"{len(open_7_plus)} production job(s) have been open 7+ days.",
                 "drill_down": "delayed_jobs"}] if open_7_plus else [])
        ),
    }


# --------------------------------------------------------------------- #
# Projects - status/progress open to all; profitability (money) reuses
# OrderService.profitability and is master-only, exactly like
# /api/dashboard/orders and /api/orders/{id}/profitability already do.
# --------------------------------------------------------------------- #
def projects_analytics(db: Session, is_privileged: bool) -> dict:
    orders = db.query(Order).options(selectinload(Order.client)).all()
    status_summary = defaultdict(int)
    for o in orders:
        status_summary[o.project_status] += 1

    on_hold = [o for o in orders if o.project_status == "On Hold"]
    now = datetime.utcnow()
    stalled = [
        o for o in orders
        if o.project_status not in ("Completed",) and o.progress_percent == 0
        and o.order_date and (now - o.order_date).days > 14
    ]

    result = {
        "total_projects": len(orders),
        "status_summary": [{"status": s, "count": c} for s, c in status_summary.items()],
        "on_hold_count": len(on_hold),
        "stalled_count": len(stalled),
        "delayed_projects": [{
            "id": o.id, "order_id": o.order_code, "client": o.client.name if o.client else None,
            "status": o.project_status, "progress_percent": o.progress_percent,
            "order_date": o.order_date.isoformat() if o.order_date else None,
        } for o in (on_hold + stalled)],
        "alerts": [],
    }
    if on_hold or stalled:
        result["alerts"].append({
            "severity": "warning",
            "message": f"{len(on_hold) + len(stalled)} project(s) are on hold or stalled with no progress.",
            "drill_down": "delayed_projects",
        })

    if is_privileged:
        profitability_rows = [OrderService.profitability(db, o) for o in orders]
        total_value = sum(r["order_value"] for r in profitability_rows)
        total_profit = sum(r["estimated_gross_profit"] for r in profitability_rows)
        result["order_profitability"] = profitability_rows
        result["overall_gross_margin_percent"] = round((total_profit / total_value) * 100, 2) if total_value else 0.0
        low_margin = [r for r in profitability_rows if r["order_value"] > 0 and r["gross_margin_percent"] < 0.1]
        if low_margin:
            result["alerts"].append({
                "severity": "warning",
                "message": f"{len(low_margin)} order(s) have a gross margin under 10%.",
                "drill_down": "order_profitability",
            })
    else:
        result["order_profitability"] = []
        result["overall_gross_margin_percent"] = None

    return result


# --------------------------------------------------------------------- #
# Tasks - open to all roles; DailyTask has no financial fields.
# --------------------------------------------------------------------- #
def tasks_analytics(db: Session) -> dict:
    tasks = db.query(DailyTask).options(selectinload(DailyTask.employee), selectinload(DailyTask.order)).all()
    status_summary = defaultdict(int)
    for t in tasks:
        status_summary[t.status] += 1

    now = datetime.utcnow()
    overdue = [t for t in tasks if t.status != "DONE" and t.date and t.date < now]
    completed = [t for t in tasks if t.status == "DONE"]
    completion_rate = round(len(completed) / len(tasks) * 100, 1) if tasks else 0.0

    return {
        "total_tasks": len(tasks),
        "status_summary": [{"status": s, "count": c} for s, c in status_summary.items()],
        "completion_rate_percent": completion_rate,
        "overdue_count": len(overdue),
        "overdue_tasks": [{
            "id": t.id, "task_id": t.task_code, "task": t.task_description,
            "employee": t.employee.name if t.employee else None,
            "order": t.order.order_code if t.order else None,
            "date": t.date.isoformat() if t.date else None, "status": t.status,
        } for t in overdue[:25]],
        "alerts": (
            [{"severity": "warning", "message": f"{len(overdue)} task(s) are overdue.", "drill_down": "overdue_tasks"}]
            if overdue else []
        ),
    }


# --------------------------------------------------------------------- #
# Payments - master-only, matching payments.py's own require_role gate.
# --------------------------------------------------------------------- #
def payments_analytics(db: Session, months: int = 6) -> dict:
    payments = db.query(Payment).options(
        selectinload(Payment.order).selectinload(Order.client)
    ).order_by(Payment.date.desc()).all()
    total = sum(float(p.amount or 0) for p in payments)

    month_keys = _last_n_months(months)
    trend = defaultdict(float)
    for p in payments:
        if p.date:
            trend[_month_key(p.date)] += float(p.amount or 0)

    by_type = defaultdict(float)
    for p in payments:
        by_type[p.payment_type] += float(p.amount or 0)

    return {
        "total_payments": len(payments),
        "total_amount": total,
        "payment_trend": [{"month": m, "value": trend.get(m, 0)} for m in month_keys],
        "by_payment_type": [{"type": k, "amount": v} for k, v in by_type.items()],
        "recent_payments": [{
            "id": p.id, "receipt_id": p.business_id, "order": p.order.order_code if p.order else None,
            "client": p.order.client.name if p.order and p.order.client else None,
            "amount": float(p.amount or 0), "mode": p.payment_mode, "date": p.date.isoformat() if p.date else None,
        } for p in payments[:25]],
    }


# --------------------------------------------------------------------- #
# Expenses - master-only (ProjectExpense has no non-financial view;
# every field is money-adjacent), matching project_expenses.py's own
# require_role gate.
# --------------------------------------------------------------------- #
def expenses_analytics(db: Session, months: int = 6) -> dict:
    expenses = db.query(ProjectExpense).options(selectinload(ProjectExpense.order)).order_by(
        ProjectExpense.date.desc()
    ).all()
    total = sum(float(e.amount or 0) for e in expenses)

    month_keys = _last_n_months(months)
    trend = defaultdict(float)
    for e in expenses:
        if e.date:
            trend[_month_key(e.date)] += float(e.amount or 0)

    by_category = defaultdict(float)
    for e in expenses:
        by_category[e.category or "Uncategorized"] += float(e.amount or 0)

    this_month, last_month = month_keys[-1], month_keys[-2] if len(month_keys) > 1 else month_keys[-1]
    this_month_total = trend.get(this_month, 0)
    last_month_total = trend.get(last_month, 0)
    change_percent = (
        round(((this_month_total - last_month_total) / last_month_total) * 100, 1)
        if last_month_total else None
    )

    # "Why did expenses increase" grounding: category breakdown for the
    # current month vs the previous month, computed only from real rows -
    # if there isn't enough data to isolate a cause, the AI layer that
    # consumes this must say so rather than guess.
    this_month_by_category = defaultdict(float)
    last_month_by_category = defaultdict(float)
    for e in expenses:
        if not e.date:
            continue
        key = _month_key(e.date)
        if key == this_month:
            this_month_by_category[e.category or "Uncategorized"] += float(e.amount or 0)
        elif key == last_month:
            last_month_by_category[e.category or "Uncategorized"] += float(e.amount or 0)
    category_deltas = [
        {
            "category": cat,
            "this_month": this_month_by_category.get(cat, 0.0),
            "last_month": last_month_by_category.get(cat, 0.0),
            "delta": this_month_by_category.get(cat, 0.0) - last_month_by_category.get(cat, 0.0),
        }
        for cat in set(list(this_month_by_category.keys()) + list(last_month_by_category.keys()))
    ]
    category_deltas.sort(key=lambda r: r["delta"], reverse=True)

    return {
        "total_expenses": total,
        "expense_trend": [{"month": m, "value": trend.get(m, 0)} for m in month_keys],
        "expense_change_percent": change_percent,
        "by_category": [{"category": k, "amount": v} for k, v in by_category.items()],
        "category_change_this_month": category_deltas,
        "recent_expenses": [{
            "id": e.id, "expense_id": e.business_id, "order": e.order.order_code if e.order else None,
            "category": e.category, "amount": float(e.amount or 0), "date": e.date.isoformat() if e.date else None,
            "paid_to": e.paid_to,
        } for e in expenses[:25]],
        "alerts": (
            [{"severity": "warning", "message": f"Expenses this month are up {change_percent:.1f}% versus last month.",
              "drill_down": "category_change_this_month"}]
            if change_percent is not None and change_percent >= 25 else []
        ),
    }


# --------------------------------------------------------------------- #
# Workforce / HR - own-record scoping is applied by the caller (route
# passes an employee_id filter for non-master viewers, same pattern
# staff dashboard uses for employee_performance).
# --------------------------------------------------------------------- #
def workforce_analytics(db: Session, is_privileged: bool, own_employee_id: Optional[int] = None) -> dict:
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    tasks = db.query(DailyTask).all()
    attendance = db.query(Attendance).all()

    now = datetime.utcnow()
    total_overtime = sum(a.overtime_hours for a in attendance)
    total_working_hours = sum(a.working_hours for a in attendance)

    performance = []
    for e in employees:
        emp_tasks = [t for t in tasks if t.employee_id == e.id]
        completed = [t for t in emp_tasks if t.status == "DONE"]
        overdue = [t for t in emp_tasks if t.date and t.date < now and t.status != "DONE"]
        emp_attendance = [a for a in attendance if a.employee_id == e.id]
        performance.append({
            "employee_id": e.id, "employee": e.name, "department": e.department,
            "tasks": len(emp_tasks), "completed": len(completed), "overdue": len(overdue),
            "completion_percent": round(len(completed) / len(emp_tasks) * 100, 1) if emp_tasks else 0.0,
            "hours": round(sum(a.working_hours for a in emp_attendance), 2),
            "overtime": round(sum(a.overtime_hours for a in emp_attendance), 2),
        })

    by_department = defaultdict(int)
    for e in employees:
        by_department[e.department or "Unassigned"] += 1

    # HR boundary: a non-privileged, non-master viewer only ever sees
    # their OWN row, not the roster - same rule the staff dashboard
    # already applies to employee_performance.
    visible_performance = performance if is_privileged else [
        p for p in performance if p["employee_id"] == own_employee_id
    ]

    return {
        "active_employees": len(employees),
        "by_department": [{"department": k, "count": v} for k, v in by_department.items()],
        "total_overtime_hours": round(total_overtime, 2),
        "total_working_hours": round(total_working_hours, 2),
        "employee_performance": visible_performance,
        "alerts": (
            [{"severity": "warning", "message": f"{sum(1 for p in visible_performance if p['overdue'] > 0)} employee(s) have overdue tasks.",
              "drill_down": "employee_performance"}]
            if is_privileged and any(p["overdue"] > 0 for p in visible_performance) else []
        ),
    }


# --------------------------------------------------------------------- #
# Operations - a cross-domain "what changed this month" rollup, built
# entirely from the same underlying counts/values the other functions
# above already computed, not a new source of truth.
# --------------------------------------------------------------------- #
def operations_analytics(db: Session, is_privileged: bool) -> dict:
    materials = db.query(Material).all()
    orders = db.query(Order).all()
    jobs = db.query(ProductionJob).all()
    tasks = db.query(DailyTask).all()
    suppliers = db.query(Supplier).count()
    clients = db.query(Client).count()

    active_orders = [o for o in orders if o.project_status != "Completed"]
    now = datetime.utcnow()
    open_jobs = [j for j in jobs if j.status != "Completed"]
    open_tasks = [t for t in tasks if t.status != "DONE"]

    return {
        "active_orders": len(active_orders),
        "open_production_jobs": len(open_jobs),
        "open_tasks": len(open_tasks),
        "total_materials": len(materials),
        "total_suppliers": suppliers,
        "total_clients": clients,
        "low_stock_items": len([m for m in materials if 0 < (m.current_stock or 0) <= (m.minimum_stock or 0)]),
        "out_of_stock_items": len([m for m in materials if (m.current_stock or 0) <= 0]),
        "total_stock_value": round(sum(m.stock_value for m in materials), 2) if is_privileged else None,
    }


# --------------------------------------------------------------------- #
# "What changed this month" - a grounded cross-domain comparison for AI
# explain-style questions. Every figure here is re-derived from the
# functions above (same authoritative sums), never a new calculation.
# --------------------------------------------------------------------- #
def month_over_month_summary(db: Session, is_privileged: bool) -> dict:
    sales = sales_revenue_outstanding(db) if is_privileged else None
    expenses = expenses_analytics(db) if is_privileged else None
    production = production_analytics(db)
    tasks = tasks_analytics(db)

    changes = []
    if sales and sales["revenue_change_percent"] is not None:
        direction = "up" if sales["revenue_change_percent"] >= 0 else "down"
        changes.append(f"Revenue received is {direction} {abs(sales['revenue_change_percent']):.1f}% versus last month.")
    if expenses and expenses["expense_change_percent"] is not None:
        direction = "up" if expenses["expense_change_percent"] >= 0 else "down"
        changes.append(f"Expenses are {direction} {abs(expenses['expense_change_percent']):.1f}% versus last month.")
    if production["blocked_count"]:
        changes.append(f"{production['blocked_count']} production job(s) are currently blocked.")
    if tasks["overdue_count"]:
        changes.append(f"{tasks['overdue_count']} task(s) are overdue.")

    if not changes:
        changes.append("No significant month-over-month changes were found in the available data.")

    return {
        "summary_lines": changes,
        "revenue_change_percent": sales["revenue_change_percent"] if sales else None,
        "expense_change_percent": expenses["expense_change_percent"] if expenses else None,
        "expense_category_deltas": expenses["category_change_this_month"] if expenses else [],
    }
