"""Family 21 - "Provide a safe development/demo reset."

A single master-only endpoint that clears every table the demo seed
(scripts/seed_sample_data.py) populates, then re-runs that exact same
seed function - so "reset" and "seed from empty" are guaranteed to
produce identical results, not two independently-maintained code paths
that could drift apart.

Deliberately NEVER touches: `users` (would delete/lock out whoever is
using the app, including any real accounts created since setup - a
"safe" reset must not do that), `audit_logs` (the audit trail is meant
to survive exactly this kind of operation - the reset itself is logged
into it, not erased by it), `id_counters` (the global ID sequence stays
monotonically increasing across a reset - a new record after a reset
must never reuse a business_id a deleted record already had), and the
lookup/settings tables (Unit, Department, etc. - small reference lists,
not "demo transactional data", and every foreign column that uses them
stores a plain string, not a real FK, so there is nothing to break by
leaving them as-is).

Gated two ways, both required: `require_role("master")` (route-level
RBAC, same as every other destructive endpoint in this app) AND
`ENVIRONMENT != "production"` (a hard 403 regardless of role) - a
demo-data reset must never be reachable against a real production
database no matter who is asking.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_role
from app.core.audit import log_action

from app.models.notification import Notification
from app.models.task_comment import TaskComment
from app.models.order_comment import OrderComment
from app.models.stock_ledger_entry import StockLedgerEntry
from app.models.production_job import ProductionJob
from app.models.daily_task import DailyTask
from app.models.issue import Issue
from app.models.purchase import Purchase
from app.models.supplier_material import SupplierMaterial
from app.models.project_expense import ProjectExpense
from app.models.payment_document import PaymentDocument
from app.models.payment import Payment
from app.models.client_document import ClientDocument
from app.models.generic_document import GenericDocument
from app.models.milestone import Milestone
from app.models.order_item import OrderItem
from app.models.estimate_line_item import EstimateLineItem
from app.models.salary_slip import SalarySlip
from app.models.leave import Leave
from app.models.attendance import Attendance
from app.models.interview import Interview
from app.models.candidate import Candidate
from app.models.working_calendar import CompanyHoliday
from app.models.order import Order
from app.models.estimate import Estimate
from app.models.product_material import ProductMaterial
from app.models.product import Product
from app.models.product_category import ProductCategory, ProductSubcategory
from app.models.employee import Employee
from app.models.client_activity import ClientActivity
from app.models.client import Client
from app.models.material_attribute import MaterialAttributeValue
from app.models.material import Material
from app.models.material_category import MaterialCategory, MaterialSubcategory
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.stock_transaction import StockTransfer, StockAdjustment

from scripts.seed_sample_data import run_seed

router = APIRouter(prefix="/api/demo", tags=["demo"])

# Children before parents - anything with a foreign key to another
# table in this list is deleted before that table.
_RESET_ORDER = [
    Notification, TaskComment, OrderComment, StockLedgerEntry,
    ProductionJob, DailyTask, Issue, StockTransfer, StockAdjustment,
    Purchase, SupplierMaterial, ProjectExpense,
    PaymentDocument, Payment, ClientDocument, GenericDocument,
    Milestone, OrderItem, EstimateLineItem,
    SalarySlip, Leave, Attendance, Interview, Candidate, CompanyHoliday,
    # Estimate holds the FK to Order (Estimate.order_id) - must be
    # deleted before Order, not after.
    Estimate, Order,
    ProductMaterial, Product, ProductSubcategory, ProductCategory,
    Employee, ClientActivity, Client,
    MaterialAttributeValue, Material, MaterialSubcategory, MaterialCategory,
    Location, Supplier,
]


@router.post("/reset")
def reset_demo_data(request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if settings.is_production:
        raise HTTPException(status_code=403, detail="The demo reset is not available in production.")

    deleted_counts = {}
    for model in _RESET_ORDER:
        count = db.query(model).delete(synchronize_session=False)
        deleted_counts[model.__tablename__] = count
    db.commit()

    run_seed(db)

    log_action(db, request, user_id=auth.get("user_id"), action="reset_demo_data", module_name="demo",
               record_id=0, old_value={"deleted": deleted_counts}, new_value={"reseeded": True})

    return {
        "status": "reset_complete",
        "deleted": deleted_counts,
        "message": "Demo data cleared and re-seeded successfully.",
    }
