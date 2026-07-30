from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.estimate import EstimateCreate, EstimateUpdate, EstimateResponse
from app.models.estimate import Estimate
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/estimates", tags=["estimates"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[EstimateResponse])
def get_estimates(status: str = None, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Estimate)
    if status:
        query = query.filter(Estimate.status == status)
    return query.all()

@router.post("/", response_model=EstimateResponse)
def create_estimate(estimate: EstimateCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    total_cost = estimate.material_cost + estimate.labor_cost
    db_estimate = Estimate(**estimate.model_dump(), total_cost=total_cost)
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
    
    update_data = estimate.model_dump(exclude_unset=True)
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