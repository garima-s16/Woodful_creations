from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import CuttingRequirement, ProductionJob
from app.modules.operations.schemas import (
    CuttingRequirementCreate, CuttingRequirementUpdate, CuttingRequirementResponse,
)
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/cutting-requirements", tags=["cutting-requirements"])


def _serialize(requirement: CuttingRequirement) -> CuttingRequirementResponse:
    response = CuttingRequirementResponse.model_validate(requirement)
    if requirement.material:
        response.material_name = requirement.material.name
    if requirement.product:
        response.product_name = requirement.product.name
    return response


@router.get("/", response_model=List[CuttingRequirementResponse])
def list_cutting_requirements(production_job_id: Optional[int] = Query(None),
                               db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(CuttingRequirement)
    if production_job_id:
        query = query.filter(CuttingRequirement.production_job_id == production_job_id)
    rows = query.order_by(CuttingRequirement.id).all()
    return [_serialize(r) for r in rows]


@router.post("/", response_model=CuttingRequirementResponse, status_code=201)
def create_cutting_requirement(data: CuttingRequirementCreate, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    """Creating this record is planning only - it never touches
    Material.current_stock. Actual consumption still goes through
    Issue/StockService.record_issue exactly as before; this table has
    no write path into inventory at all."""
    job = db.query(ProductionJob).filter(ProductionJob.id == data.production_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    for _ in range(5):
        requirement = CuttingRequirement(**data.dict(), business_id=generate_business_id(db))
        db.add(requirement)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(requirement)
        return _serialize(requirement)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{requirement_id}", response_model=CuttingRequirementResponse)
def get_cutting_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    return _serialize(requirement)


@router.put("/{requirement_id}", response_model=CuttingRequirementResponse)
def update_cutting_requirement(requirement_id: int, data: CuttingRequirementUpdate,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return _serialize(requirement)


@router.delete("/{requirement_id}", status_code=204)
def delete_cutting_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    db.delete(requirement)
    db.commit()
