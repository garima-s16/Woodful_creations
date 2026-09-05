"""Analytics & Reporting API.

Every endpoint here delegates its actual aggregation to
app.modules.reporting.analytics_service, which reuses the same authoritative
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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.reporting import analytics_service as svc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/sales")
def sales_analytics(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.sales_revenue_outstanding(db, months=months)


@router.get("/inventory")
def inventory_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.inventory_analytics(db, is_privileged=is_privileged)


@router.get("/purchases")
def purchases_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.purchases_analytics(db, months=months)


@router.get("/production")
def production_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return svc.production_analytics(db)


@router.get("/projects")
def projects_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.projects_analytics(db, is_privileged=is_privileged)


@router.get("/tasks")
def tasks_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return svc.tasks_analytics(db)


@router.get("/payments")
def payments_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.payments_analytics(db, months=months)


@router.get("/expenses")
def expenses_analytics_route(months: int = 6, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return svc.expenses_analytics(db, months=months)


@router.get("/workforce")
def workforce_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    own_employee_id = auth.get("employee_id")
    return svc.workforce_analytics(db, is_privileged=is_privileged, own_employee_id=own_employee_id)


@router.get("/operations")
def operations_analytics_route(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.operations_analytics(db, is_privileged=is_privileged)


@router.get("/alerts")
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


@router.get("/whats-changed")
def whats_changed(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Grounded 'what changed this month' summary for the AI assistant
    and the analytics page alike - built only from real month-over-month
    comparisons already computed in analytics_service, never fabricated."""
    is_privileged = auth.get("role", "user") in ("master",)
    return svc.month_over_month_summary(db, is_privileged=is_privileged)
