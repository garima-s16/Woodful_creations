"""Computes actual working days for a given month from the configured
working calendar - the explicit requirement that no
calculation assume a fixed 26 working days. Each month is calculated
independently from the current calendar configuration; nothing here
retroactively rewrites past records if the configuration later
changes (that's the caller's responsibility, matching "do not rewrite
historical finalized payroll records")."""
import calendar
from datetime import date

from sqlalchemy.orm import Session

from app.modules.hr.models import WorkingCalendarSettings, CompanyHoliday

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def compute_working_days(db: Session, year: int, month: int) -> int:
    """Total working days in the given month, using the configured
    weekday pattern plus any date-specific holiday/special-working-day
    overrides. Falls back to "every day is a working day" only if the
    weekday config table is genuinely empty (e.g. migration not yet
    run in an older environment) - never silently assumes a fixed
    day count."""
    working_weekday_rows = db.query(WorkingCalendarSettings).all()
    if working_weekday_rows:
        working_weekdays = {row.weekday for row in working_weekday_rows if row.is_working}
    else:
        working_weekdays = set(WEEKDAY_NAMES)  # no config yet - treat every day as working

    days_in_month = calendar.monthrange(year, month)[1]
    holiday_overrides = {
        h.date: h.is_working
        for h in db.query(CompanyHoliday).filter(
            CompanyHoliday.date >= date(year, month, 1),
            CompanyHoliday.date <= date(year, month, days_in_month),
        ).all()
    }

    working_days = 0
    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        if current in holiday_overrides:
            if holiday_overrides[current]:
                working_days += 1  # declared special working day
            # else: declared holiday, does not count regardless of weekday
        elif WEEKDAY_NAMES[current.weekday()] in working_weekdays:
            working_days += 1

    return working_days
