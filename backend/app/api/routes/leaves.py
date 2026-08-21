from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.leave import Leave
from app.schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse
from app.utils.id_generator import generate_business_id

router = APIRouter(prefix="/api/leaves", tags=["leaves"])


def calculate_leave_days(start_date, end_date) -> Decimal:
    """Inclusive calendar-day count: From = To counts as 1 day, and
    From=11 Aug / To=13 Aug counts as 3 days. Computed from the date
    portion only, so a start/end that differ only in time-of-day (e.g.
    both submitted as midnight-UTC from a <input type="date">) still
    produce the correct whole-day count instead of drifting by a
    fraction of a day."""
    delta_days = (end_date.date() - start_date.date()).days + 1
    return Decimal(delta_days)


@router.get("/", response_model=List[LeaveResponse])
def list_leaves(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own leave records.")
        employee_id = own_employee_id
    query = db.query(Leave)
    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)
    if status:
        query = query.filter(Leave.status == status)
    return query.order_by(Leave.start_date.desc()).all()


@router.post("/", response_model=LeaveResponse, status_code=201)
def request_leave(data: LeaveCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",) and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only request leave for yourself.")
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")

    days = calculate_leave_days(data.start_date, data.end_date)
    if days < 1:
        # Defensive - calculate_leave_days cannot actually return <1 once the
        # end < start check above has passed, but this keeps the invariant
        # explicit and future-proof rather than implicit in the date math.
        raise HTTPException(status_code=400, detail="Number of days must be at least 1")

    leave = Leave(**data.dict(), days=days, business_id=generate_business_id(db))
    db.add(leave)
    for _ in range(5):
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            leave.business_id = generate_business_id(db)
            db.add(leave)
            continue
        db.refresh(leave)
        return leave
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.put("/{leave_id}", response_model=LeaveResponse)
def update_leave_status(leave_id: int, data: LeaveUpdate, db: Session = Depends(get_db),
                         auth=Depends(require_role("master"))):
    """Approve/reject a leave request - restricted since it's a supervisory action."""
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(leave, field, value)
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave
