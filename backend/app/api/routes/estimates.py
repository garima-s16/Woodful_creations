from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action, serializable_fields
from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.schemas.estimate import EstimateCreate, EstimateUpdate, EstimateResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


def _compute_totals(subtotal: Decimal, discount: Decimal, tax_percent: Decimal):
    """Backend is the sole authority for these figures - the frontend
    may preview a running total for UX, but this is what gets stored
    and returned. taxable = subtotal - discount; tax is applied to the
    taxable amount, not the raw subtotal."""
    taxable = subtotal - discount
    if taxable < 0:
        taxable = Decimal("0")
    tax_amount = (taxable * tax_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tax_amount, taxable + tax_amount


def _build_line_items(line_items_data, estimate_id: int = None):
    """Computes amount = quantity * rate server-side for each line item -
    the frontend may show a running total for UX, but the stored amount
    is never taken from client input directly."""
    items = []
    for idx, item in enumerate(line_items_data):
        amount = (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        items.append(EstimateLineItem(
            estimate_id=estimate_id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=amount, sort_order=idx,
        ))
    return items


def _serialize_estimates(estimates, role: str):
    """An estimate is inherently a pricing document - material_cost,
    labor_cost, discount, subtotal, tax_amount, total_cost, and each
    line item's rate/amount are genuinely nulled for non-master
    roles. status/version (workflow state, not money) stay visible."""
    responses = [EstimateResponse.model_validate(e) for e in estimates]
    if role not in ("master",):
        for r in responses:
            r.material_cost = None
            r.labor_cost = None
            r.discount = None
            r.subtotal = None
            r.tax_amount = None
            r.total_cost = None
            for item in r.line_items:
                item.rate = None
                item.amount = None
    return responses


def _serialize_estimate(estimate, role: str):
    return _serialize_estimates([estimate], role)[0]


@router.get("/", response_model=List[EstimateResponse])
def list_estimates(client_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Estimate)
    if client_id:
        query = query.filter(Estimate.client_id == client_id)
    if status:
        query = query.filter(Estimate.status == status)
    return _serialize_estimates(query.order_by(Estimate.created_at.desc()).all(), auth.get("role", "user"))


@router.post("/", response_model=EstimateResponse, status_code=201)
def create_estimate(data: EstimateCreate, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"estimate_code", "line_items"})

    if data.line_items:
        line_items = _build_line_items(data.line_items)
        subtotal = sum((item.amount for item in line_items), Decimal("0"))
        # material_cost/labor_cost are legacy summary fields - when real
        # line items are supplied, keep them in sync by category rather
        # than let them silently go stale for any report still reading
        # them directly.
        payload["material_cost"] = sum(
            (i.amount for i in line_items if i.category == "Material"), Decimal("0"))
        payload["labor_cost"] = sum(
            (i.amount for i in line_items if i.category == "Labor"), Decimal("0"))
    else:
        line_items = []
        subtotal = data.material_cost + data.labor_cost

    tax_amount, total_cost = _compute_totals(subtotal, data.discount, data.tax_percent)

    for _ in range(5):
        code = generate_unique_code(db, Estimate, "estimate_code", "EST-")
        estimate = Estimate(**payload, estimate_code=code, business_id=generate_short_id(),
                             tax_amount=tax_amount, total_cost=total_cost)
        db.add(estimate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        for item in line_items:
            item.estimate_id = estimate.id
            db.add(item)
        db.commit()
        db.refresh(estimate)
        log_action(db, request, user_id=auth.get("user_id"), action="create_estimate", module_name="estimates",
                   record_id=estimate.id, new_value={
                       "client_id": estimate.client_id, "estimate_code": estimate.estimate_code,
                       "total_cost": float(estimate.total_cost or 0),
                   })
        return estimate
    raise HTTPException(status_code=500, detail="Unable to generate a unique estimate code, please try again")


@router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return _serialize_estimate(estimate, auth.get("role", "user"))


@router.put("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(estimate_id: int, data: EstimateUpdate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    update_fields = data.dict(exclude_unset=True, exclude={"line_items"})
    old_value = serializable_fields(estimate, update_fields.keys())
    for field, value in update_fields.items():
        setattr(estimate, field, value)

    if data.line_items is not None:
        # Replace the whole set - editing an estimate's line items is a
        # "these are the current items" operation, not an incremental
        # patch, matching how the frontend's item editor works (it
        # submits the full current list, not a diff).
        for existing in list(estimate.line_items):
            db.delete(existing)
        db.flush()
        new_items = _build_line_items(data.line_items, estimate_id=estimate.id)
        for item in new_items:
            db.add(item)
        db.flush()
        subtotal = sum((item.amount for item in new_items), Decimal("0"))
        estimate.material_cost = sum((i.amount for i in new_items if i.category == "Material"), Decimal("0"))
        estimate.labor_cost = sum((i.amount for i in new_items if i.category == "Labor"), Decimal("0"))
    else:
        subtotal = estimate.subtotal

    if data.line_items is not None or any(f in update_fields for f in ("material_cost", "labor_cost", "discount", "tax_percent")):
        estimate.tax_amount, estimate.total_cost = _compute_totals(subtotal, estimate.discount, estimate.tax_percent)

    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    new_value = serializable_fields(estimate, update_fields.keys())
    if data.line_items is not None:
        new_value["items_changed"] = True
    log_action(db, request, user_id=auth.get("user_id"), action="update_estimate", module_name="estimates",
               record_id=estimate.id, old_value=old_value, new_value=new_value)
    return estimate


@router.post("/{estimate_id}/revise", response_model=EstimateResponse, status_code=201)
def revise_estimate(estimate_id: int, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Create a new version of an estimate rather than overwriting it -
    copies the source estimate's figures (including its line items) into
    a new row, incrementing the version number and always pointing
    parent_estimate_id at the root of the chain (not necessarily the
    immediate source), so /versions can find every revision with one
    query."""
    source = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Estimate not found")

    root_id = source.parent_estimate_id or source.id
    latest_version = db.query(Estimate).filter(
        (Estimate.id == root_id) | (Estimate.parent_estimate_id == root_id)
    ).order_by(Estimate.version.desc()).first()
    next_version = (latest_version.version if latest_version else source.version) + 1

    new_code = f"{source.estimate_code.split('-v')[0]}-v{next_version}"
    revision = Estimate(
        estimate_code=new_code, business_id=generate_short_id(),
        client_id=source.client_id, order_id=source.order_id,
        description=source.description, material_cost=source.material_cost, labor_cost=source.labor_cost,
        discount=source.discount, tax_percent=source.tax_percent, tax_amount=source.tax_amount,
        total_cost=source.total_cost, valid_until=source.valid_until, remarks=source.remarks,
        version=next_version, parent_estimate_id=root_id, status="draft",
    )
    db.add(revision)
    db.flush()
    for idx, item in enumerate(source.line_items):
        db.add(EstimateLineItem(
            estimate_id=revision.id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=item.amount, sort_order=idx,
        ))
    db.commit()
    db.refresh(revision)
    log_action(db, request, user_id=auth.get("user_id"), action="revise_estimate", module_name="estimates",
               record_id=revision.id, old_value={"source_estimate_id": source.id, "source_version": source.version},
               new_value={"new_version": revision.version, "estimate_code": revision.estimate_code})
    return revision


@router.get("/{estimate_id}/versions", response_model=List[EstimateResponse])
def list_estimate_versions(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every version in the same chain as estimate_id, oldest first."""
    source = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Estimate not found")

    root_id = source.parent_estimate_id or source.id
    versions = db.query(Estimate).filter(
        (Estimate.id == root_id) | (Estimate.parent_estimate_id == root_id)
    ).order_by(Estimate.version.asc()).all()
    return _serialize_estimates(versions, auth.get("role", "user"))
