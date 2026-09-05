"""Generic CRUD over every lookup/settings table, mirroring the "Settings"
sheet in each of the three source workbooks. One family of endpoints per
lookup type: /api/settings/{lookup_type}."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from app.platform.audit.audit import log_action
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.schemas.setting import LookupCreate, LookupUpdate, LookupResponse
from app.models.setting import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory, ProductionStage,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# NOTE: "material-categories" and "locations" are intentionally NOT included
# here. They graduated from simple name/description lookup rows into full
# models (app/models/material_category.py, app/models/location.py) with
# their own dedicated CRUD routers (material_categories.router,
# locations.router, registered in app/api/routes/__init__.py). Routing them
# through this generic lookup CRUD would re-introduce the duplicate-table
# mapping conflict those dedicated models replaced.
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


@router.get("/")
def list_lookup_types(auth=Depends(get_current_user)):
    return {"lookup_types": list(LOOKUP_MODELS.keys())}


@router.get("/{lookup_type}", response_model=List[LookupResponse])
def list_lookup_values(lookup_type: str, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    model = _model_or_404(lookup_type)
    return db.query(model).order_by(model.name).all()


@router.post("/{lookup_type}", response_model=LookupResponse, status_code=201)
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


@router.put("/{lookup_type}/{item_id}", response_model=LookupResponse)
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


@router.delete("/{lookup_type}/{item_id}", status_code=204)
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
