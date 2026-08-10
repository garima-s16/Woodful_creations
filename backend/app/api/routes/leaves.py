from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.leave import Leave
from app.schemas.leave import LeaveCreate, LeaveUpdate, LeaveResponse

router = APIRouter(prefix="/api/leaves", tags=["leaves"])


@router.get("/", response_model=List[LeaveResponse])
def list_leaves(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Leave)
    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)
    if status:
        query = query.filter(Leave.status == status)
    return query.order_by(Leave.start_date.desc()).all()


@router.post("/", response_model=LeaveResponse, status_code=201)
def request_leave(data: LeaveCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    leave = Leave(**data.dict())
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.put("/{leave_id}", response_model=LeaveResponse)
def update_leave_status(leave_id: int, data: LeaveUpdate, db: Session = Depends(get_db),
                         auth=Depends(require_role("master", "manager"))):
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
