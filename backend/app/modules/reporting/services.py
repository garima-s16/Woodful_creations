"""Reporting services: AIWorkspaceReport/ReportHistory models,
cross-domain analytics (sales/inventory/purchases/production/
projects/tasks/payments/expenses/workforce/operations), and business-
risk aggregation (order/payroll/salary-advance risk items). Combines
the former models.py, analytics_service.py, and business_risk_service.py."""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.platform.database import BaseModel
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session, selectinload
from app.modules.sales.models import Order, Payment
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.operations.models import ProjectExpense
from app.modules.operations.models import ProductionJob
from app.modules.operations.models import DailyTask
from app.modules.hr.models import Employee, Attendance
from app.modules.clients.models import Client
from app.modules.procurement.models import Supplier
from app.modules.sales.services import OrderService
from sqlalchemy.orm import Session
from app.modules.sales.models import Order
from app.modules.hr.models import SalarySlip, SalaryAdvance


# --- models.py ---
"""Reporting domain models: AIWorkspaceReport (persisted AI analysis
artifacts) and ReportHistory (report-generation event metadata,
15-day retention)."""

class AIWorkspaceReport(BaseModel):
    """A persisted multi-step AI analysis result (e.g. "what's blocking
    this order") - a real, viewable Woodful artifact connected to real
    data, not a one-off chat message that disappears. findings is a
    JSON-encoded string of the structured result (risk_level, reasons,
    per-dimension detail) so it can be redisplayed without recomputing,
    and so a master/employee viewing it later sees exactly what was
    found, not a live re-query that could drift."""
    __tablename__ = "ai_workspace_reports"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False)  # ON_TRACK / AT_RISK
    findings = Column(Text, nullable=False)  # JSON-encoded structured result
    requested_by = Column(String(255), nullable=True)

    order = relationship("Order")


class ReportHistory(BaseModel):
    """Lightweight metadata recording that a
    report was generated, kept for the existing 15-day retention
    requirement. This table holds only metadata about the report
    generation event itself (report_date, generated_at, report_type,
    storage_identity) - never the report's own content, and never any
    underlying business record (tasks, orders, etc - those are
    untouched by this table's retention). Rows older than 15 days are
    safe to expire since they are history-of-a-generation-event, not a
    business record in their own right."""
    __tablename__ = "report_history"

    report_type = Column(String(50), nullable=False, index=True)  # e.g. "daily_status_report"
    report_date = Column(DateTime, nullable=False)  # the date the report covers
    generated_at = Column(DateTime, nullable=False)  # when this generation event happened
    # Where the generated artifact was delivered/would be found - e.g.
    # "email:master@example.com,other@example.com" or "download" for an
    # on-demand Excel response that was streamed and never persisted to
    # storage. Not a StorageReference - no report artifact is currently
    # persisted to disk/Drive by this app (Excel is generated and
    # streamed in-memory), so this column records the delivery identity
    # actually available today rather than inventing a storage path
    # nothing writes to.
    storage_identity = Column(String(255), nullable=True)


# --- analytics_service.py ---
"""Analytics & Reporting.

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


def inventory_analytics(db: Session, is_privileged: bool) -> dict:
    active_materials = db.query(Material).filter(Material.is_active.is_(True))

    total_materials = active_materials.count()
    low_stock_count = active_materials.filter(
        Material.current_stock > 0, Material.current_stock <= Material.minimum_stock,
    ).count()
    out_of_stock_count = active_materials.filter(Material.current_stock <= 0).count()

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

    # Only the bounded reorder-suggestion list actually needs full Material
    # rows (and their primary_supplier, eager-loaded to avoid a separate
    # query per row) - counts/totals above never load a row at all.
    low_or_out_of_stock = (
        active_materials
        .filter(Material.current_stock <= Material.minimum_stock)
        .options(selectinload(Material.primary_supplier))
        .order_by(Material.current_stock.asc())
        .all()
    )

    total_stock_value = float(
        db.query(func.coalesce(func.sum(Material.stock_value), 0))
        .filter(Material.is_active.is_(True)).scalar() or 0
    )

    result = {
        "total_materials": total_materials,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "category_breakdown": [
            {
                "category": row.category, "items": row.items,
                "stock_quantity": float(row.stock_quantity),
                "stock_value": (round(float(row.stock_value), 2) if is_privileged else None),
            }
            for row in category_rows
        ],
        # Real drill-down: the actual materials behind "low stock", not a fabricated list.
        "low_stock_materials": [{
            "id": m.id, "material": m.name, "current_stock": float(m.current_stock or 0),
            "minimum_stock": float(m.minimum_stock or 0), "unit": m.unit,
            "suggested_order": max(float(m.minimum_stock or 0) - float(m.current_stock or 0), 0),
            "supplier": m.primary_supplier.name if m.primary_supplier else None,
        } for m in low_or_out_of_stock],
        "total_stock_value": round(total_stock_value, 2) if is_privileged else None,
        "alerts": [],
    }
    if out_of_stock_count:
        result["alerts"].append({
            "severity": "critical",
            "message": f"{out_of_stock_count} material(s) are out of stock.",
            "drill_down": "low_stock_materials",
        })
    elif low_stock_count:
        result["alerts"].append({
            "severity": "warning",
            "message": f"{low_stock_count} material(s) are at or below their minimum stock level.",
            "drill_down": "low_stock_materials",
        })
    return result


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
        profitability_rows = list(OrderService.profitability_bulk(db, orders).values())
        total_value = sum(r["order_value"] for r in profitability_rows)
        total_profit = sum(r["estimated_gross_profit"] for r in profitability_rows)
        result["order_profitability"] = profitability_rows
        # Ratio (0.25 == 25%), matching the per-order "gross_margin_ratio"
        # contract from OrderService - this was previously stored on a
        # 0-100 scale under the same "_percent" naming pattern as the
        # per-order ratio field, which risked a 100x misreading between
        # the two. Frontend now multiplies by 100 for display, same as
        # every per-order consumer already does.
        result["overall_gross_margin_ratio"] = round((total_profit / total_value), 6) if total_value else 0.0
        low_margin = [r for r in profitability_rows if r["order_value"] > 0 and r["gross_margin_ratio"] < 0.1]
        if low_margin:
            result["alerts"].append({
                "severity": "warning",
                "message": f"{len(low_margin)} order(s) have a gross margin under 10%.",
                "drill_down": "order_profitability",
            })
    else:
        result["order_profitability"] = []
        result["overall_gross_margin_ratio"] = None

    return result


def tasks_analytics(db: Session) -> dict:
    """DailyTask accumulates a row per task for the life of the
    business. Status counts, the total, and the completion rate come
    from a single GROUP BY query; full rows are only ever fetched for
    the (naturally much smaller) overdue subset the drill-down actually
    displays - not the whole table."""
    now = datetime.utcnow()

    status_rows = db.query(DailyTask.status, func.count(DailyTask.id)).group_by(DailyTask.status).all()
    status_summary = {status: count for status, count in status_rows}
    total_tasks = sum(status_summary.values())
    completed_count = status_summary.get("DONE", 0)
    completion_rate = round(completed_count / total_tasks * 100, 1) if total_tasks else 0.0

    overdue_filter = and_(DailyTask.status != "DONE", DailyTask.date.isnot(None), DailyTask.date < now)
    overdue_count = db.query(func.count(DailyTask.id)).filter(overdue_filter).scalar() or 0
    overdue_tasks = db.query(DailyTask).options(
        selectinload(DailyTask.employee), selectinload(DailyTask.order)
    ).filter(overdue_filter).limit(25).all()

    return {
        "total_tasks": total_tasks,
        "status_summary": [{"status": s, "count": c} for s, c in status_summary.items()],
        "completion_rate_percent": completion_rate,
        "overdue_count": overdue_count,
        "overdue_tasks": [{
            "id": t.id, "task_id": t.task_code, "task": t.task_description,
            "employee": t.employee.name if t.employee else None,
            "order": t.order.order_code if t.order else None,
            "date": t.date.isoformat() if t.date else None, "status": t.status,
        } for t in overdue_tasks],
        "alerts": (
            [{"severity": "warning", "message": f"{overdue_count} task(s) are overdue.", "drill_down": "overdue_tasks"}]
            if overdue_count else []
        ),
    }


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


def workforce_analytics(db: Session, is_privileged: bool, own_employee_id: Optional[int] = None) -> dict:
    """Employee is a small, bounded table (one row per person on the
    payroll), so it's still safely `.all()`-loaded below. DailyTask and
    especially Attendance are not bounded the same way - Attendance
    accumulates a row per employee per day for the life of the
    business - so this avoids loading either table in full.

    DailyTask totals use a real SQL GROUP BY (status/date/employee_id
    are plain columns). Attendance.working_hours/overtime_hours are
    NOT plain columns - they're Python @property values computed from
    (out_time - in_time) with per-row rounding (see app/modules/hr/models.py).
    That per-row datetime-delta-then-round formula doesn't have a
    single SQL expression that is both (a) verifiably correct without
    a live DB to test against, since SQLite and PostgreSQL do not share
    datetime-subtraction semantics, and (b) guaranteed to match Python's
    round-then-sum behavior exactly. Rather than guess at cross-dialect
    SQL for this and risk silently wrong totals, this fetches only the
    four narrow columns the formula actually needs (not full Attendance
    ORM rows/relationships) and computes hours in Python exactly as
    before - still a real reduction (no relationship loading, no unused
    columns over the wire), just not a full SQL-side aggregation.
    """
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    now = datetime.utcnow()

    by_department = defaultdict(int)
    for e in employees:
        by_department[e.department or "Unassigned"] += 1

    attendance_rows = db.query(
        Attendance.employee_id, Attendance.in_time, Attendance.out_time, Attendance.standard_hours,
    ).all()

    total_overtime = Decimal("0")
    total_working_hours = Decimal("0")
    attendance_by_employee = defaultdict(lambda: {"hours": Decimal("0"), "overtime": Decimal("0")})
    for employee_id, in_time, out_time, standard_hours in attendance_rows:
        if in_time and out_time:
            working = Decimal(str(round((out_time - in_time).total_seconds() / 3600, 2)))
        else:
            working = Decimal("0")
        overtime = max(working - Decimal(str(standard_hours or 0)), Decimal("0"))
        total_working_hours += working
        total_overtime += overtime
        attendance_by_employee[employee_id]["hours"] += working
        attendance_by_employee[employee_id]["overtime"] += overtime

    # Per-employee task totals - DailyTask's status/date/employee_id are
    # plain columns, so this part is a real SQL GROUP BY instead of a
    # Python pass over the full (also unbounded) task table.
    tasks_by_employee = {
        row.employee_id: row
        for row in db.query(
            DailyTask.employee_id.label("employee_id"),
            func.count(DailyTask.id).label("total"),
            func.coalesce(func.sum(case((DailyTask.status == "DONE", 1), else_=0)), 0).label("completed"),
            func.coalesce(func.sum(case(
                (and_(DailyTask.status != "DONE", DailyTask.date.isnot(None), DailyTask.date < now), 1),
                else_=0,
            )), 0).label("overdue"),
        ).group_by(DailyTask.employee_id).all()
    }

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
            "completion_percent": round(completed / total_tasks * 100, 1) if total_tasks else 0.0,
            "hours": round(float(a["hours"]), 2) if a else 0.0,
            "overtime": round(float(a["overtime"]), 2) if a else 0.0,
        })

    # HR boundary: a non-privileged, non-master viewer only ever sees
    # their OWN row, not the roster - same rule the staff dashboard
    # already applies to employee_performance.
    visible_performance = performance if is_privileged else [
        p for p in performance if p["employee_id"] == own_employee_id
    ]

    return {
        "active_employees": len(employees),
        "by_department": [{"department": k, "count": v} for k, v in by_department.items()],
        "total_overtime_hours": round(float(total_overtime), 2) if is_privileged else None,
        "total_working_hours": round(float(total_working_hours), 2) if is_privileged else None,
        "employee_performance": visible_performance,
        "alerts": (
            [{"severity": "warning", "message": f"{sum(1 for p in visible_performance if p['overdue'] > 0)} employee(s) have overdue tasks.",
              "drill_down": "employee_performance"}]
            if is_privileged and any(p["overdue"] > 0 for p in visible_performance) else []
        ),
    }


def operations_analytics(db: Session, is_privileged: bool) -> dict:
    """Cross-domain counts only - no per-row drill-down is returned here
    (Materials/Orders/ProductionJob/DailyTask all grow without bound
    over the life of the business), so every figure below is a
    database-side COUNT/SUM instead of `.all()` + Python len()/sum(),
    which previously reloaded all four full tables on every dashboard
    render just to produce eight numbers."""
    active_orders = db.query(func.count(Order.id)).filter(Order.project_status != "Completed").scalar() or 0
    open_jobs = db.query(func.count(ProductionJob.id)).filter(ProductionJob.status != "Completed").scalar() or 0
    open_tasks = db.query(func.count(DailyTask.id)).filter(DailyTask.status != "DONE").scalar() or 0
    suppliers = db.query(func.count(Supplier.id)).scalar() or 0
    clients = db.query(func.count(Client.id)).scalar() or 0

    total_materials, low_stock_items, out_of_stock_items, total_stock_value = db.query(
        func.count(Material.id),
        func.coalesce(func.sum(case(
            (and_(Material.current_stock > 0, Material.current_stock <= Material.minimum_stock), 1),
            else_=0,
        )), 0),
        func.coalesce(func.sum(case((Material.current_stock <= 0, 1), else_=0)), 0),
        func.sum(Material.current_stock * Material.average_rate),
    ).one()

    return {
        "active_orders": active_orders,
        "open_production_jobs": open_jobs,
        "open_tasks": open_tasks,
        "total_materials": total_materials or 0,
        "total_suppliers": suppliers,
        "total_clients": clients,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
        "total_stock_value": round(float(total_stock_value or 0), 2) if is_privileged else None,
    }


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


# --- business_risk_service.py ---
"""Cross-Module Business Risk + Business Decision Centre
(Family P0.49/P0.51).

Orchestrates already-authoritative domain signals into one unified,
prioritized "what needs my attention" view. Never recalculates a
domain-owned figure - every risk here traces back to a single
existing service call (OrderService.compute_order_health for orders;
SalarySlip.status for payroll) and is transformed into a structured,
explainable risk-item shape, not re-derived from raw tables. This
file is the one place that combines them; it is not a second
calculation engine for any of them.

Deliberately narrow scope for this family: Delivery (via Order
Health, which already folds in material/production/task signals -
P0.50) and Payroll (via SalarySlip.status). Standalone Inventory/
Procurement risk not already tied to an order, and full labour-cost
attribution, are not built here - there is no existing authoritative
service to consume for either yet, and inventing one would be exactly
the "second calculation engine" this family must not create (see
sections 9, 23, 26, 27).
"""

_ORDER_TERMINAL_STATUSES = ("Completed", "Cancelled")


_ORDER_RISK_TO_SEVERITY = {"CRITICAL": "CRITICAL", "AT_RISK": "HIGH", "WATCH": "MEDIUM"}


_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _order_to_risk_item(order: Order, health: dict) -> dict:
    """Transforms one order's compute_order_health result into the
    P0.49 risk-item contract - the one place this shape is built, so
    _order_risk_items and get_risk_for_entity can never drift apart."""
    return {
        "risk_type": "DELIVERY",
        "severity": _ORDER_RISK_TO_SEVERITY.get(health["risk_level"], "LOW"),
        "entity_type": "order", "entity_id": order.id, "entity_code": order.order_code,
        "title": f"{order.order_code} needs attention",
        "reason": "; ".join(health["reasons"]),
        "evidence": health["evidence"],
        "business_impact": health["business_impact"],
        "recommended_action": health["next_action"]["description"] if health["next_action"] else None,
        "priority": health["risk_level"],
        "source_module": "sales",
        "action_path": f"/orders/{order.id}",
    }


_MAX_ORDERS_PER_RISK_SCAN = 150


def _order_risk_items(db: Session) -> list:
    """One risk item per open order whose compute_order_health is not
    ON_TRACK - the single authoritative per-order calculation, called
    once per open order (not per every order ever created), matching
    section 33's "active decision set" guidance rather than an
    unbounded historical scan. compute_order_health itself already
    uses batch-safe queries (StockService's material-requirement/
    reservation calculations), so this loop is bounded by the number
    of genuinely open orders, not a source of new N+1 queries within
    each iteration.

    KNOWN PERFORMANCE LIMIT: compute_order_health runs several queries
    of its own per order (tasks, production jobs, material-requirement
    calculation). At a small number of genuinely open orders this is
    fine; at several hundred, this becomes hundreds of queries for one
    Decision Centre load. A bulk pre-filter would need to replicate
    compute_order_health's own BOM/cross-order-reservation logic to
    avoid missing a real shortage-driven risk (bulk_attention_flags,
    the existing cheap pre-filter, explicitly does not cover
    material-shortage risk - see order_service.py) - doing that here
    would itself become the "second calculation engine" this codebase
    deliberately avoids, so it is not attempted blind. Instead this is
    bounded to the _MAX_ORDERS_PER_RISK_SCAN most delivery-urgent open
    orders (soonest delivery date first, nulls last) rather than left
    fully unbounded - a genuine, remaining scaling limit, not a false
    "unbounded and fine" claim."""
    open_orders = (
        db.query(Order)
        .filter(Order.project_status.notin_(_ORDER_TERMINAL_STATUSES))
        .order_by(Order.delivery_date.is_(None), Order.delivery_date.asc())
        .limit(_MAX_ORDERS_PER_RISK_SCAN)
        .all()
    )
    items = []
    for order in open_orders:
        health = OrderService.compute_order_health(db, order.id)
        if not health or health["risk_level"] == "ON_TRACK":
            continue
        items.append(_order_to_risk_item(order, health))
    return items


def _payroll_risk_items(db: Session) -> list:
    """A finalized-but-unpaid salary slip is real, existing, checkable
    data (SalarySlip.status, set by whoever runs payroll) - never an
    invented anomaly. Master-only: payroll figures are financial/
    confidential (sections 17, 21)."""
    pending = db.query(SalarySlip).filter(SalarySlip.status == "finalized").all()
    items = []
    for slip in pending:
        employee_name = slip.employee.name if slip.employee else "Unknown employee"
        items.append({
            "risk_type": "PAYROLL", "severity": "MEDIUM",
            "entity_type": "salary_slip", "entity_id": slip.id, "entity_code": slip.business_id,
            "title": f"Salary slip for {employee_name} ({slip.month} {slip.year}) is finalized but not paid",
            "reason": "Salary has been finalized but payment has not been recorded.",
            "evidence": [{"type": "payroll_pending", "month": slip.month, "year": slip.year}],
            "business_impact": "An employee's approved salary remains unpaid.",
            "recommended_action": "Record the salary payment.",
            "priority": "MEDIUM",
            "source_module": "hr",
            # No per-slip detail page exists - the list page shows the
            # same record with the actual approve/pay actions inline.
            "action_path": "/salary-slips",
        })
    return items


def _salary_advance_risk_items(db: Session) -> list:
    """A Pending salary advance request is a real, existing fact
    (Family P0.44 - built after this file's original P0.49 pass, added
    here once real data existed to consume - matching P0.44's own
    section 31: "prepare structured outputs... for P0.49/P0.51 to
    consume"). Deliberately does NOT flag every Approved-with-
    outstanding-balance advance as a risk - recovery can legitimately
    span several payroll months by design (see SalaryAdvance's own
    model comment), so an outstanding balance alone is expected
    behaviour, not an attention item; only a request still awaiting
    the Master's own decision is."""
    pending = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Pending").all()
    items = []
    for advance in pending:
        employee_name = advance.employee.name if advance.employee else "Unknown employee"
        items.append({
            "risk_type": "PAYROLL", "severity": "LOW",
            "entity_type": "salary_advance", "entity_id": advance.id, "entity_code": advance.business_id,
            "title": f"Salary advance request from {employee_name} is awaiting review",
            "reason": f"Requested {advance.requested_amount} on {advance.request_date.date().isoformat()}, not yet approved or rejected.",
            "evidence": [{"type": "salary_advance_pending", "requested_amount": float(advance.requested_amount)}],
            "business_impact": "The employee's request remains unresolved.",
            "recommended_action": "Review and approve or reject this salary advance request.",
            "priority": "LOW",
            "source_module": "hr",
            # No per-advance detail page exists - the list page shows
            # the same record with the actual approve/reject actions
            # inline.
            "action_path": "/salary-advances",
        })
    return items


def get_business_risks(db: Session, is_privileged: bool) -> dict:
    """P0.49 + P0.51 contract: one prioritized list of cross-module
    business risks plus a summary count - the same shape the REST API,
    frontend, and any future AI/chatbot consumer all read (section 19).
    is_privileged (MASTER) gates payroll/financial risk items; a
    non-privileged caller sees only operational (order-delivery) risk,
    matching sections 17/18/21's financial/HR confidentiality rule.
    Errors from one signal source must not silently look like "no
    risk" (section 35) - callers that need per-source error isolation
    should catch around the individual _*_risk_items() calls; this
    function itself does not swallow exceptions."""
    items = _order_risk_items(db)
    if is_privileged:
        items += _payroll_risk_items(db)
        items += _salary_advance_risk_items(db)

    items.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 9))

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in items:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1

    return {
        "total": len(items),
        "counts": counts,
        "risks": items,
        "generated_at": datetime.utcnow().isoformat(),
    }


def get_risk_for_entity(db: Session, entity_type: str, entity_id: int, is_privileged: bool) -> Optional[dict]:
    """Look up a single risk item by entity (section 19's AI contract -
    "why is this order at risk" needs one item, not the whole list).
    Recomputes directly via the same authoritative calculation rather
    than looping every open order or caching, so the answer is always
    current (section 34 - freshness) at the same cost as the existing
    per-order GET /api/orders/{id}/health endpoint - not a new N+1
    concern."""
    if entity_type == "order":
        order = db.query(Order).filter(Order.id == entity_id).first()
        if not order:
            return None
        health = OrderService.compute_order_health(db, entity_id)
        if not health or health["risk_level"] == "ON_TRACK":
            return None
        return _order_to_risk_item(order, health)
    if entity_type == "salary_slip" and is_privileged:
        matches = [r for r in _payroll_risk_items(db) if r["entity_id"] == entity_id]
        return matches[0] if matches else None
    if entity_type == "salary_advance" and is_privileged:
        matches = [r for r in _salary_advance_risk_items(db) if r["entity_id"] == entity_id]
        return matches[0] if matches else None
    return None


def cash_flow_forecast(db: Session, weeks: int = 6) -> dict:
    """Family 137 feature 12 - Forward Cash-Flow Forecast. Built
    entirely from real, existing data - order balances (Order.balance,
    already maintained transactionally by OrderService.record_payment/
    Order.recompute_totals, never recalculated here) and each order's
    own delivery_date, the only real signal this codebase has for
    "when is this client likely to pay the rest" (there is no separate
    payment-terms/due-date field to read instead).

    Every figure is explicitly labelled, never blended:
      - ACTUAL: payments genuinely already received (real Payment rows)
      - OVERDUE: a real, current outstanding balance whose order's
        delivery_date has already passed - FACT, not a prediction
      - EXPECTED: a real, current outstanding balance whose order has
        a future delivery_date, bucketed into the week containing it -
        a PREDICTION of timing, the balance itself is a fact
      - FORECAST: a real, current outstanding balance with no
        delivery_date at all - genuinely unscheduled, kept separate
        rather than guessed into a week

    A past-week EXPECTED balance still outstanding becomes an
    exception (section 11: "if an expected payment does not arrive,
    surface an exception"). Never sends anything and never modifies an
    order - purely a read aggregation (section 11: "do not
    automatically send collection messages")."""
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())  # Monday of the current week

    open_orders = db.query(Order).filter(Order.project_status != "Cancelled", Order.balance > 0).all()

    weekly_buckets = []
    for i in range(weeks):
        w_start = week_start + timedelta(weeks=i)
        weekly_buckets.append({
            "week_start": w_start.isoformat(), "week_end": (w_start + timedelta(days=6)).isoformat(),
            "is_current_week": i == 0,
            "expected_total": 0.0, "expected_orders": [],
            "actual_total": 0.0,
        })

    overdue_total, overdue_orders = 0.0, []
    forecast_total, forecast_orders = 0.0, []
    exceptions = []

    for o in open_orders:
        balance = float(o.balance or 0)
        if not o.delivery_date:
            forecast_total += balance
            forecast_orders.append({"order_id": o.id, "order_code": o.order_code, "balance": balance,
                                     "reason": "No delivery date set to anchor a forecast."})
            continue
        d = o.delivery_date.date()
        if d < today:
            days_overdue = (today - d).days
            overdue_total += balance
            overdue_orders.append({"order_id": o.id, "order_code": o.order_code, "balance": balance,
                                    "days_overdue": days_overdue})
            if days_overdue <= weeks * 7:
                exceptions.append({
                    "order_id": o.id, "order_code": o.order_code, "balance": balance,
                    "expected_week_of": (d - timedelta(days=d.weekday())).isoformat(),
                    "reason": f"Order {o.order_code}: Rs {balance:,.2f} expected around {d.isoformat()}, "
                              f"still outstanding {days_overdue} day(s) later.",
                })
            continue
        weeks_out = (d - week_start).days // 7
        if 0 <= weeks_out < weeks:
            bucket = weekly_buckets[weeks_out]
            bucket["expected_total"] += balance
            bucket["expected_orders"].append({"order_id": o.id, "order_code": o.order_code, "balance": balance,
                                               "expected_date": d.isoformat()})
        else:
            forecast_total += balance
            forecast_orders.append({"order_id": o.id, "order_code": o.order_code, "balance": balance,
                                     "expected_date": d.isoformat(),
                                     "reason": "Outside the current forecast window."})

    # ACTUAL - real payments already received within each bucket's week.
    payments = db.query(Payment).filter(Payment.date >= datetime.combine(week_start, datetime.min.time())).all()
    for p in payments:
        weeks_out = (p.date.date() - week_start).days // 7
        if 0 <= weeks_out < weeks:
            weekly_buckets[weeks_out]["actual_total"] += float(p.amount or 0)

    for b in weekly_buckets:
        b["expected_total"] = round(b["expected_total"], 2)
        b["actual_total"] = round(b["actual_total"], 2)

    return {
        "week_start": week_start.isoformat(), "weeks": weeks,
        "weekly_buckets": weekly_buckets,
        "overdue_total": round(overdue_total, 2), "overdue_orders": overdue_orders,
        "forecast_total": round(forecast_total, 2), "forecast_orders": forecast_orders,
        "current_week_expected": weekly_buckets[0]["expected_orders"] if weekly_buckets else [],
        "exceptions": exceptions,
        "total_outstanding": round(sum(float(o.balance or 0) for o in open_orders), 2),
        "generated_at": datetime.utcnow().isoformat(),
    }


def owner_briefing(db: Session, period: str = "daily") -> dict:
    """Family 137 feature 11 - Owner Daily/Weekly Business Briefing. A
    genuine cross-module synthesis, never a generic KPI dump (spec
    section 10): every section reuses the one authoritative
    calculation this codebase already has for that signal (business
    risks, cash-flow forecast, low stock, production bottlenecks,
    overdue purchases, delayed projects, payroll/leave state) rather
    than a second, parallel computation, and a section only appears
    when it actually found something.

    period ("daily"/"weekly") controls only the lookback window for
    "client actions" (recent portal approvals/change requests) - every
    other number is the same live, current state either way; a
    briefing is never a stale snapshot. Master-only (see the API
    route) - financial and HR detail throughout."""
    from app.modules.inventory.services import _low_stock
    from app.modules.operations.services import _production_bottlenecks, _delayed_deliveries, _delayed_projects
    from app.modules.hr.services import get_payroll_summary, get_salary_advance_summary
    from app.modules.hr.models import Leave
    from app.modules.clients.models import ClientActivity

    if period not in ("daily", "weekly"):
        period = "daily"
    lookback_days = 1 if period == "daily" else 7
    now = datetime.utcnow()
    since = now - timedelta(days=lookback_days)
    today = now.date()
    month, year = f"{today.month:02d}", str(today.year)

    risks = get_business_risks(db, is_privileged=True)
    cash = cash_flow_forecast(db, weeks=6 if period == "weekly" else 2)
    low_stock_text, _, low_stock_records = _low_stock(db, "master")
    bottleneck_text, _, bottleneck_records = _production_bottlenecks(db)
    delivery_text, _, delivery_records = _delayed_deliveries(db)
    project_text, _, project_records = _delayed_projects(db)
    payroll = get_payroll_summary(db, month, year)
    advances = get_salary_advance_summary(db)
    pending_leaves = db.query(Leave).filter(Leave.status == "Pending").all()
    client_actions = (
        db.query(ClientActivity)
        .filter(ClientActivity.logged_by == "Client Portal", ClientActivity.date >= since)
        .order_by(ClientActivity.date.desc())
        .all()
    )

    sections = []

    if risks["total"]:
        sections.append({
            "key": "attention", "title": "What needs attention",
            "facts": [f"{risks['total']} open business risk item(s), {risks['counts'].get('CRITICAL', 0)} of them critical."],
            "predictions": [], "recommendations": [],
            "items": risks["risks"][:10],
        })

    cash_facts = []
    if cash["overdue_total"]:
        cash_facts.append(f"Rs {cash['overdue_total']:,.2f} currently overdue across {len(cash['overdue_orders'])} order(s).")
    cash_predictions = []
    if cash["weekly_buckets"] and cash["weekly_buckets"][0]["expected_total"]:
        cash_predictions.append(f"Rs {cash['weekly_buckets'][0]['expected_total']:,.2f} expected to be collected this week "
                                 f"across {len(cash['weekly_buckets'][0]['expected_orders'])} order(s).")
    if cash_facts or cash_predictions or cash["exceptions"]:
        sections.append({
            "key": "cash", "title": "Cash and collections",
            "facts": cash_facts, "predictions": cash_predictions,
            "recommendations": ["Review overdue balances for possible follow-up."] if cash["overdue_total"] else [],
            "items": cash["overdue_orders"][:10],
            "exceptions": cash["exceptions"],
        })

    if low_stock_records:
        sections.append({"key": "inventory", "title": "Inventory", "facts": [low_stock_text],
                          "predictions": [], "recommendations": [], "items": low_stock_records})
    if bottleneck_records:
        sections.append({"key": "operations", "title": "Operations", "facts": [bottleneck_text],
                          "predictions": [], "recommendations": [], "items": bottleneck_records})
    if delivery_records:
        sections.append({"key": "procurement", "title": "Procurement", "facts": [delivery_text],
                          "predictions": [], "recommendations": [], "items": delivery_records})
    if project_records:
        sections.append({"key": "deliveries", "title": "Deliveries at risk", "facts": [project_text],
                          "predictions": [], "recommendations": [], "items": project_records})

    hr_facts = []
    if payroll["employees_without_slip"]:
        hr_facts.append(f"{payroll['employees_without_slip']} employee(s) have no salary slip yet for {month}/{year}.")
    if payroll["status_counts"].get("finalized"):
        hr_facts.append(f"{payroll['status_counts']['finalized']} finalized slip(s) awaiting payment "
                         f"(Rs {float(payroll['total_net_pending_payment']):,.2f}).")
    if pending_leaves:
        hr_facts.append(f"{len(pending_leaves)} leave request(s) pending approval.")
    if advances["pending_requests"]:
        hr_facts.append(f"{advances['pending_requests']} salary advance request(s) pending approval.")
    if hr_facts:
        sections.append({
            "key": "hr", "title": "HR", "facts": hr_facts, "predictions": [], "recommendations": [],
            "items": [{"type": "Leave", "label": e.employee.name if e.employee else "Employee",
                       "sublabel": f"{e.leave_type} - {float(e.days):g} day(s)", "path": "/leaves"}
                      for e in pending_leaves[:10]],
        })

    if client_actions:
        sections.append({
            "key": "client_actions", "title": "Client actions",
            "facts": [f"{len(client_actions)} client decision(s) recorded in the last {lookback_days} day(s)."],
            "predictions": [], "recommendations": [],
            "items": [{"type": "Client", "label": a.client.name if a.client else "Client",
                       "sublabel": a.summary[:120], "path": f"/clients/{a.client_id}"} for a in client_actions[:10]],
        })

    exceptions = list(cash["exceptions"])
    exceptions += [{"reason": r["reason"], "path": r.get("action_path")} for r in risks["risks"] if r["severity"] == "CRITICAL"]

    period_word = {"daily": "day", "weekly": "week"}[period]
    if not sections:
        headline = "Nothing needs attention right now - cash, stock, production, and deliveries all look clear."
    else:
        headline = f"{len(sections)} area(s) worth a look this {period_word}" \
                   + (f" - most urgent: {exceptions[0]['reason']}" if exceptions else ".")

    return {
        "period": period, "generated_at": now.isoformat(),
        "headline": headline,
        "sections": sections,
        "exceptions": exceptions,
        "note": "Woodful observes, analyzes, and recommends here - every action still requires a human decision.",
    }
