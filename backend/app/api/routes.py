"""Top-level platform API routes (settings lookups, audit logs)
and the master router aggregation used by main.py. Combines the
former settings.py, audit_logs.py, and __init__.py."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from app.platform.audit import log_action, AuditLog, AuditLogResponse
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.schemas.setting import LookupCreate, LookupUpdate, LookupResponse
from app.models import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory, ProductionStage,
)
from app.modules.auth import auth as auth_module
from app.modules.procurement import api as procurement_module
from app.modules.inventory import api as inventory_module
from app.modules.catalog import api as catalog_module
from app.modules.hr import api as hr_module
from app.modules.clients import api as clients_module
from app.modules.clients import portal_api as client_portal_module
from app.modules.communications import api as communications_module
from app.modules.operations import api_operations as ops_module
from app.modules.operations import api_production as prod_module
from app.modules.reporting import api as reporting_module
from app.modules.sales import api as sales_module
from app.modules.recruitment import module as recruitment_module
from app.modules.ai import api as ai_module
from app.modules.documents import api as documents


# --- settings.py ---
settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


LOOKUP_MODELS = {
    "units": Unit,
    "stock-statuses": StockStatus,
    "stock-payment-statuses": StockPaymentStatus,
    "supplier-terms": SupplierTerm,
    "departments": Department,
    "task-statuses": TaskStatus,
    "attendance-statuses": AttendanceStatus,
    "machines": Machine,
    "project-statuses": ProjectStatus,
    "priorities": Priority,
    "payment-modes": PaymentMode,
    "lead-sources": LeadSource,
    "project-types": ProjectType,
    "expense-categories": ExpenseCategory,
    "production-stages": ProductionStage,
}


def _model_or_404(lookup_type: str):
    model = LOOKUP_MODELS.get(lookup_type)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown settings list: {lookup_type}")
    return model


@settings_router.get("/")
def list_lookup_types(auth=Depends(get_current_user)):
    return {"lookup_types": list(LOOKUP_MODELS.keys())}


@settings_router.get("/{lookup_type}", response_model=List[LookupResponse])
def list_lookup_values(lookup_type: str, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    model = _model_or_404(lookup_type)
    return db.query(model).order_by(model.name).all()


@settings_router.post("/{lookup_type}", response_model=LookupResponse, status_code=201)
def add_lookup_value(lookup_type: str, item: LookupCreate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    model = _model_or_404(lookup_type)
    if db.query(model).filter(model.name == item.name).first():
        raise HTTPException(status_code=400, detail="This value already exists")
    row = model(**item.dict())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@settings_router.put("/{lookup_type}/{item_id}", response_model=LookupResponse)
def update_lookup_value(lookup_type: str, item_id: int, item: LookupUpdate,
                         db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    model = _model_or_404(lookup_type)
    row = db.query(model).filter(model.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Value not found")
    for field, value in item.dict(exclude_unset=True).items():
        setattr(row, field, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@settings_router.delete("/{lookup_type}/{item_id}", status_code=204)
def delete_lookup_value(lookup_type: str, item_id: int, request: Request, db: Session = Depends(get_db),
                         auth=Depends(require_role("master"))):
    model = _model_or_404(lookup_type)
    row = db.query(model).filter(model.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Value not found")
    row_name = getattr(row, "name", None)
    db.delete(row)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_lookup_value", module_name="settings",
               record_id=item_id, old_value={"lookup_type": lookup_type, "name": row_name})


# --- audit_logs.py ---
audit_logs_router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@audit_logs_router.get("/", response_model=List[AuditLogResponse])
def list_audit_logs(
    module_name: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth=Depends(require_role("master")),
):
    query = db.query(AuditLog)
    if module_name:
        query = query.filter(AuditLog.module_name == module_name)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


# --- __init__.py (master router aggregation) ---
all_routers = [
    auth_module.auth_router,
    settings_router,
    procurement_module.suppliers_router,
    inventory_module.materials_router,
    inventory_module.material_categories_router,
    catalog_module.products_router,
    catalog_module.product_imports_router,
    inventory_module.material_imports_router,
    hr_module.holiday_imports_router,
    clients_module.client_imports_router,
    catalog_module.rate_cards_router,
    catalog_module.rate_card_imports_router,
    clients_module.product_rate_router,
    procurement_module.supplier_materials_router,
    inventory_module.locations_router,
    communications_module.notifications_router,
    inventory_module.stock_transactions_router,
    procurement_module.purchase_imports_router,
    procurement_module.personal_cart_router,
    procurement_module.purchases_router,
    procurement_module.procurement_requirements_router,
    ops_module.issues_router,
    clients_module.clients_router,
    clients_module.activity_router,
    client_portal_module.client_portal_router,
    reporting_module.search_router,
    sales_module.orders_router,
    sales_module.order_imports_router,
    sales_module.payments_router,
    ops_module.project_expenses_router,
    hr_module.employees_router,
    hr_module.attendance_router,
    hr_module.overtime_requests_router,
    hr_module.leaves_router,
    ops_module.daily_tasks_router,
    prod_module.production_jobs_router,
    prod_module.production_operations_router,
    ops_module.work_centres_router,
    prod_module.cutting_requirements_router,
    reporting_module.dashboard_router,
    reporting_module.business_decisions_router,
    inventory_module.reports_router,
    sales_module.reports_router,
    hr_module.reports_router,
    ops_module.reports_router,
    clients_module.reports_router,
    catalog_module.reports_router,
    sales_module.estimates_router,
    sales_module.estimate_imports_router,
    recruitment_module.candidates_router,
    recruitment_module.interviews_router,
    hr_module.salary_slips_router,
    hr_module.salary_advances_router,
    ai_module.chat_router,
    auth_module.users_router,
    audit_logs_router,
    hr_module.working_calendar_router,
    ops_module.milestones_router,
    documents.router,
    ai_module.agents_router,
    communications_module.automation_router,
    communications_module.communication_router,
    reporting_module.analytics_router,
]
