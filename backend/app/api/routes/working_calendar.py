from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action
from app.models.working_calendar import WorkingCalendarSettings, CompanyHoliday
from app.schemas.working_calendar import (
    WorkingWeekdayUpdate, WorkingWeekdayResponse,
    CompanyHolidayCreate, CompanyHolidayResponse,
)
from app.services.working_calendar_service import compute_working_days

router = APIRouter(prefix="/api/working-calendar", tags=["working-calendar"])


@router.get("/weekdays", response_model=List[WorkingWeekdayResponse])
def list_weekdays(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Readable by any authenticated user (the calendar affects
    everyone's attendance/payroll context), editable by master only."""
    return db.query(WorkingCalendarSettings).order_by(WorkingCalendarSettings.id).all()


@router.put("/weekdays/{weekday_id}", response_model=WorkingWeekdayResponse)
def update_weekday(weekday_id: int, data: WorkingWeekdayUpdate, request: Request,
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    row = db.query(WorkingCalendarSettings).filter(WorkingCalendarSettings.id == weekday_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Weekday setting not found")
    old_value = row.is_working
    row.is_working = data.is_working
    db.add(row)
    db.commit()
    db.refresh(row)
    log_action(db, request, user_id=auth.get("user_id"), action="update_working_weekday",
               module_name="working_calendar", record_id=row.id,
               old_value={"weekday": row.weekday, "is_working": old_value},
               new_value={"weekday": row.weekday, "is_working": row.is_working})
    return row


@router.get("/holidays", response_model=List[CompanyHolidayResponse])
def list_holidays(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(CompanyHoliday).order_by(CompanyHoliday.date).all()


@router.post("/holidays", response_model=CompanyHolidayResponse, status_code=201)
def create_holiday(data: CompanyHolidayCreate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    if db.query(CompanyHoliday).filter(CompanyHoliday.date == data.date).first():
        raise HTTPException(status_code=400, detail="A calendar override already exists for this date")
    holiday = CompanyHoliday(**data.dict())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    log_action(db, request, user_id=auth.get("user_id"), action="create_company_holiday",
               module_name="working_calendar", record_id=holiday.id,
               new_value={"date": str(holiday.date), "name": holiday.name, "is_working": holiday.is_working})
    return holiday


@router.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    holiday = db.query(CompanyHoliday).filter(CompanyHoliday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    old_value = {"date": str(holiday.date), "name": holiday.name}
    db.delete(holiday)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_company_holiday",
               module_name="working_calendar", record_id=holiday_id, old_value=old_value)


@router.get("/working-days")
def get_working_days(year: int, month: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Read-only: the computed working-day count for a given month,
    using the current calendar configuration. Any authenticated user
    can check this (it's not sensitive), matching how the weekday
    list itself is also readable by anyone."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="month must be between 1 and 12")
    return {"year": year, "month": month, "working_days": compute_working_days(db, year, month)}
