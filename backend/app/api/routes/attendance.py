from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.attendance import Attendance
from app.schemas.attendance import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("/", response_model=List[AttendanceResponse])
def list_attendance(employee_id: Optional[int] = Query(None), date: Optional[datetime] = Query(None),
                     db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own attendance records.")
        employee_id = own_employee_id
    query = db.query(Attendance)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if date:
        query = query.filter(Attendance.date == date)
    return query.order_by(Attendance.date.desc()).all()


@router.post("/", response_model=AttendanceResponse, status_code=201)
def mark_attendance(data: AttendanceCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",) and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only mark attendance for yourself.")
    for _ in range(5):
        record = Attendance(**data.dict(), business_id=generate_short_id(db))
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(record)
        return record
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.put("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(attendance_id: int, data: AttendanceUpdate, db: Session = Depends(get_db),
                       auth=Depends(require_role("master"))):
    """Correcting a logged attendance record is a supervisory action,
    same as approving/rejecting a leave request."""
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(record, field, value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
