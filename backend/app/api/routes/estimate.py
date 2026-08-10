from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user as verify_auth
from app.models.estimate import Estimate
from app.schemas.estimate import EstimateCreate, EstimateResponse, EstimateUpdate

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


@router.get("/", response_model=list[EstimateResponse])
def get_estimates(status: str | None = None, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Estimate)
    if status:
        query = query.filter(Estimate.status == status)
    return query.all()


@router.post("/", response_model=EstimateResponse)
def create_estimate(estimate: EstimateCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    total_cost = estimate.material_cost + estimate.labor_cost
    db_estimate = Estimate(**estimate.dict(), total_cost=total_cost)
    db.add(db_estimate)
    db.commit()
    db.refresh(db_estimate)
    return db_estimate


@router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return estimate


@router.patch("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(estimate_id: int, estimate: EstimateUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not db_estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    update_data = estimate.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_estimate, key, value)

    if "material_cost" in update_data or "labor_cost" in update_data:
        db_estimate.total_cost = db_estimate.material_cost + db_estimate.labor_cost

    db.add(db_estimate)
    db.commit()
    db.refresh(db_estimate)
    return db_estimate


@router.delete("/{estimate_id}")
def delete_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    db.delete(estimate)
    db.commit()
    return {"message": "Estimate deleted"}
