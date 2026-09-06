from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import ProductionOperation, ProductionJob
from app.modules.operations.schemas import (
    ProductionOperationCreate, ProductionOperationUpdate, ProductionOperationResponse,
)
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/production-operations", tags=["production-operations"])

# Matching ProductionJob's and DailyTask's established pattern: any
# employee can update direct work-progress fields on any operation -
# planning fields (sequence, dependency, which job it belongs to)
# remain master-only.
EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "actual_duration_minutes", "start_time", "end_time"}


@router.get("/", response_model=List[ProductionOperationResponse])
def list_production_operations(production_job_id: Optional[int] = Query(None),
                                db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on))
    if production_job_id:
        query = query.filter(ProductionOperation.production_job_id == production_job_id)
    return query.order_by(ProductionOperation.production_job_id, ProductionOperation.sequence).all()


@router.post("/", response_model=ProductionOperationResponse, status_code=201)
def create_production_operation(data: ProductionOperationCreate, db: Session = Depends(get_db),
                                 auth=Depends(require_role("master"))):
    job = db.query(ProductionJob).filter(ProductionJob.id == data.production_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    if data.depends_on_operation_id:
        predecessor = db.query(ProductionOperation).filter(
            ProductionOperation.id == data.depends_on_operation_id,
        ).first()
        if not predecessor:
            raise HTTPException(status_code=404, detail="Dependency operation not found")
        if predecessor.production_job_id != data.production_job_id:
            raise HTTPException(status_code=400, detail="An operation can only depend on another operation within the same production job")

    for _ in range(5):
        operation = ProductionOperation(**data.dict(), business_id=generate_business_id(db))
        db.add(operation)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(operation)
        return operation
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{operation_id}", response_model=ProductionOperationResponse)
def get_production_operation(operation_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    operation = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on)).filter(
        ProductionOperation.id == operation_id,
    ).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Production operation not found")
    return operation


@router.put("/{operation_id}", response_model=ProductionOperationResponse)
def update_production_operation(operation_id: int, data: ProductionOperationUpdate,
                                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    # Locked before checking/setting status - same reasoning as
    # ProductionJob's update: two simultaneous updates to the same
    # operation must not both read the same pre-update state.
    operation = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on)).filter(
        ProductionOperation.id == operation_id,
    ).with_for_update().first()
    if not operation:
        raise HTTPException(status_code=404, detail="Production operation not found")

    role = auth.get("role", "user")
    update_data = data.dict(exclude_unset=True)

    if role not in ("master",):
        disallowed = set(update_data.keys()) - EMPLOYEE_SELF_SERVICE_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"You can only update: {', '.join(sorted(EMPLOYEE_SELF_SERVICE_FIELDS))}. "
                       f"Not allowed to change: {', '.join(sorted(disallowed))}.",
            )

    # Real enforcement, not just informational display (P0.3.4): a
    # dependent operation cannot actually be started or completed while
    # its declared predecessor is still incomplete.
    if update_data.get("status") in ("In Progress", "Completed") and operation.is_blocked_by_dependency:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This operation depends on \"{operation.depends_on.operation_name}\", which is still "
                f"{operation.depends_on.status}. Complete it first."
            ),
        )

    for field, value in update_data.items():
        setattr(operation, field, value)
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation
