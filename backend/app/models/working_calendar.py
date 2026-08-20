from sqlalchemy import Column, String, Date, Boolean, Text
from app.models.base import BaseModel


class WorkingCalendarSettings(BaseModel):
    """Single-row configuration: which weekdays are working days by
    default. A separate row per weekday (rather than one JSON blob)
    keeps this readable and directly editable via the existing
    Settings-page CRUD pattern, matching how every other lookup list
    in this app already works.

    weekday: 0=Monday ... 6=Sunday (Python's datetime.weekday() convention)."""
    __tablename__ = "working_calendar_weekdays"

    weekday = Column(String(10), unique=True, nullable=False)  # "Monday".."Sunday"
    is_working = Column(Boolean, nullable=False, default=True)


class CompanyHoliday(BaseModel):
    """A single calendar-date override. is_working=False means a
    company holiday (removes an otherwise-working day). is_working=True
    on a normally-off weekday means a declared special working day
    (adds a working day back). One table covers both cases from
    Section 4/5's requirements, rather than two separate models."""
    __tablename__ = "company_holidays"

    date = Column(Date, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_working = Column(Boolean, nullable=False, default=False)  # False = holiday, True = special working day
    remarks = Column(Text, nullable=True)
