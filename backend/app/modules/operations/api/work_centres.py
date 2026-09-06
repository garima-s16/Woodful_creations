from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import WorkCentre
from app.modules.operations.schemas import WorkCentreCreate, WorkCentreUpdate, WorkCentreResponse
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/work-centres", tags=["work-centres"])


@router.get("/", response_model=List[WorkCentreResponse])
def list_work_centres(active_only: bool = Query(False), db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(WorkCentre)
    if active_only:
        query = query.filter(WorkCentre.is_active.is_(True))
    return query.order_by(WorkCentre.name).all()


@router.post("/", response_model=WorkCentreResponse, status_code=201)
def create_work_centre(data: WorkCentreCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    for _ in range(5):
        centre = WorkCentre(**data.dict(), business_id=generate_business_id(db))
        db.add(centre)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.query(WorkCentre).filter(WorkCentre.name == data.name).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"A work centre named \"{data.name}\" already exists.")
            continue
        db.refresh(centre)
        return centre
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{work_centre_id}", response_model=WorkCentreResponse)
def get_work_centre(work_centre_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    return centre


@router.put("/{work_centre_id}", response_model=WorkCentreResponse)
def update_work_centre(work_centre_id: int, data: WorkCentreUpdate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(centre, field, value)
    db.add(centre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"A work centre named \"{data.name}\" already exists.")
    db.refresh(centre)
    return centre


@router.get("/{work_centre_id}/capacity")
def get_work_centre_capacity(work_centre_id: int, date: Optional[str] = Query(None),
                              db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """P0.3.6 - real capacity awareness: sums estimated_duration_minutes
    of every operation actually assigned to this work centre on the
    given date (via start_time's date), compares against the work
    centre's own configured capacity_hours_per_day. Never claims a
    conflict without real, existing scheduled operations behind it."""
    from datetime import datetime as dt
    from app.modules.operations.models import ProductionOperation

    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    if centre.capacity_hours_per_day is None:
        return {
            "work_centre_id": work_centre_id, "has_capacity_data": False,
            "message": "No daily capacity is configured for this work centre.",
        }

    target_date = dt.fromisoformat(date).date() if date else dt.utcnow().date()
    operations = db.query(ProductionOperation).filter(
        ProductionOperation.work_centre_id == work_centre_id,
        ProductionOperation.status != "Completed",
    ).all()
    scheduled_minutes = sum(
        (op.estimated_duration_minutes or 0) for op in operations
        if op.start_time and op.start_time.date() == target_date
    )
    capacity_minutes = float(centre.capacity_hours_per_day) * 60
    remaining_minutes = capacity_minutes - scheduled_minutes

    return {
        "work_centre_id": work_centre_id, "has_capacity_data": True, "date": target_date.isoformat(),
        "capacity_minutes": capacity_minutes, "scheduled_minutes": scheduled_minutes,
        "remaining_minutes": remaining_minutes,
        "status": "CAPACITY_CONFLICT" if remaining_minutes < 0 else "OK",
    }
