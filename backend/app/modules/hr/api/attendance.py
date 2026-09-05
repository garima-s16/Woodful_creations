from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.hr.models import Attendance
from app.modules.hr.schemas import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("/", response_model=List[AttendanceResponse])
def list_attendance(employee_id: Optional[int] = Query(None), date: Optional[datetime] = Query(None),
                     db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own attendance records.")
        if not own_employee_id:
            # Not linked to an employee at all - "own records only" has
            # nothing to resolve to, so the honest answer is none, not
            # every employee's records (which is what an unfiltered
            # query below would otherwise silently return).
            return []
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

    # One authoritative attendance record per
    # employee per calendar day. Compared by date range rather than
    # exact equality, since the date column can carry a time component
    # and two records for "the same day" could otherwise have
    # different timestamps and slip past a naive comparison.
    day_start = datetime(data.date.year, data.date.month, data.date.day)
    day_end = day_start + timedelta(days=1)
    existing = db.query(Attendance).filter(
        Attendance.employee_id == data.employee_id,
        Attendance.date >= day_start, Attendance.date < day_end,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Attendance for this employee on {data.date.strftime('%d %b %Y')} is already recorded "
                   f"(record #{existing.id}). Use the update endpoint to correct it instead.",
        )

    for _ in range(5):
        record = Attendance(**data.dict(), business_id=generate_business_id(db))
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
    updates = data.dict(exclude_unset=True)
    effective_in_time = updates.get("in_time", record.in_time)
    effective_out_time = updates.get("out_time", record.out_time)
    if effective_in_time is not None and effective_out_time is not None and effective_out_time < effective_in_time:
        raise HTTPException(status_code=422, detail="Out time cannot be before in time")
    for field, value in updates.items():
        setattr(record, field, value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
