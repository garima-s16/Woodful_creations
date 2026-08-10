from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.estimate import Estimate
from app.schemas.estimate import EstimateCreate, EstimateUpdate, EstimateResponse

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
    if db.query(Estimate).filter(Estimate.estimate_code == data.estimate_code).first():
        raise HTTPException(status_code=400, detail="Estimate code already exists")
    tax_amount, total_cost = _compute_totals(data.material_cost, data.labor_cost, data.tax_percent)
    estimate = Estimate(**data.dict(), tax_amount=tax_amount, total_cost=total_cost)
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


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
