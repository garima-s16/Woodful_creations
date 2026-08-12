from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.estimate import Estimate
from app.schemas.estimate import EstimateCreate, EstimateUpdate, EstimateResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


def _compute_totals(material_cost: Decimal, labor_cost: Decimal, tax_percent: Decimal):
    subtotal = material_cost + labor_cost
    tax_amount = (subtotal * tax_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tax_amount, subtotal + tax_amount


@router.get("/", response_model=List[EstimateResponse])
def list_estimates(client_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Estimate)
    if client_id:
        query = query.filter(Estimate.client_id == client_id)
    if status:
        query = query.filter(Estimate.status == status)
    return query.order_by(Estimate.created_at.desc()).all()


@router.post("/", response_model=EstimateResponse, status_code=201)
def create_estimate(data: EstimateCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    payload = data.dict(exclude={"estimate_code"})
    tax_amount, total_cost = _compute_totals(data.material_cost, data.labor_cost, data.tax_percent)
    for _ in range(5):
        code = generate_unique_code(db, Estimate, "estimate_code", "EST-")
        estimate = Estimate(**payload, estimate_code=code, business_id=generate_short_id(), tax_amount=tax_amount, total_cost=total_cost)
        db.add(estimate)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(estimate)
        return estimate
    raise HTTPException(status_code=500, detail="Unable to generate a unique estimate code, please try again")


@router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return estimate


@router.put("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(estimate_id: int, data: EstimateUpdate, db: Session = Depends(get_db),
                     auth=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(estimate, field, value)
    if any(f in data.dict(exclude_unset=True) for f in ("material_cost", "labor_cost", "tax_percent")):
        estimate.tax_amount, estimate.total_cost = _compute_totals(
            estimate.material_cost, estimate.labor_cost, estimate.tax_percent
        )
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


@router.post("/{estimate_id}/revise", response_model=EstimateResponse, status_code=201)
def revise_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Create a new version of an estimate rather than overwriting it -
    copies the source estimate's figures into a new row, incrementing the
    version number and always pointing parent_estimate_id at the root of
    the chain (not necessarily the immediate source), so /versions can
    find every revision with one query."""
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
        estimate_code=new_code, client_id=source.client_id, order_id=source.order_id,
        description=source.description, material_cost=source.material_cost, labor_cost=source.labor_cost,
        tax_percent=source.tax_percent, tax_amount=source.tax_amount, total_cost=source.total_cost,
        valid_until=source.valid_until, remarks=source.remarks,
        version=next_version, parent_estimate_id=root_id, status="draft",
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
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
    return versions
