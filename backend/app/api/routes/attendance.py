from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from sqlalchemy.orm import Session
from app.schemas.attendance import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.models.attendance import Attendance
from app.core.database import get_db
from app.core.security import verify_token
from typing import List
from datetime import datetime

router = APIRouter(prefix="/api/attendance", tags=["attendance"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[AttendanceResponse])
def get_attendance(employee_id: int = Query(None), db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Attendance)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    return query.all()

@router.post("/", response_model=AttendanceResponse)
def mark_attendance(attendance: AttendanceCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_attendance = Attendance(**attendance.dict())
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance

@router.get("/{attendance_id}", response_model=AttendanceResponse)
def get_attendance_record(attendance_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return attendance

@router.patch("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(attendance_id: int, attendance: AttendanceUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    update_data = attendance.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_attendance, key, value)
    
    if db_attendance.check_in and db_attendance.check_out:
        hours = (db_attendance.check_out - db_attendance.check_in).total_seconds() / 3600
        db_attendance.hours_worked = round(hours, 2)
    
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance