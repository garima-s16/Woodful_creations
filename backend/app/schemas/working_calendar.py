from datetime import date as date_type
from typing import Optional
from pydantic import BaseModel


class WorkingWeekdayUpdate(BaseModel):
    is_working: bool


class WorkingWeekdayResponse(BaseModel):
    id: int
    weekday: str
    is_working: bool

    class Config:
        from_attributes = True


class CompanyHolidayBase(BaseModel):
    date: date_type
    name: str
    is_working: bool = False  # False = holiday, True = declared special working day
    remarks: Optional[str] = None


class CompanyHolidayCreate(CompanyHolidayBase):
    pass


class CompanyHolidayResponse(CompanyHolidayBase):
    id: int

    class Config:
        from_attributes = True
