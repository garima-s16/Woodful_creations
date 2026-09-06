"""Computes actual working days for a given month from the configured
working calendar - the explicit requirement that no
calculation assume a fixed 26 working days. Each month is calculated
independently from the current calendar configuration; nothing here
retroactively rewrites past records if the configuration later
changes (that's the caller's responsibility, matching "do not rewrite
historical finalized payroll records")."""
import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.modules.hr.models import WorkingCalendarSettings, CompanyHoliday

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_working_dates(db: Session, year: int, month: int) -> set:
    """The actual set of working calendar dates in the given month
    (not just a count) - the single place this weekday+holiday logic
    lives; compute_working_days and compute_salary_days both use this
    rather than each re-deriving it. Falls back to "every day is a
    working day" only if the weekday config table is genuinely empty
    (e.g. migration not yet run in an older environment) - never
    silently assumes a fixed day count."""
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

    working_dates = set()
    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        if current in holiday_overrides:
            if holiday_overrides[current]:
                working_dates.add(current)  # declared special working day
            # else: declared holiday, does not count regardless of weekday
        elif WEEKDAY_NAMES[current.weekday()] in working_weekdays:
            working_dates.add(current)
    return working_dates


def compute_working_days(db: Session, year: int, month: int) -> int:
    """Total working days in the given month, using the configured
    weekday pattern plus any date-specific holiday/special-working-day
    overrides. Never silently assumes a fixed day count."""
    return len(get_working_dates(db, year, month))


def compute_salary_days(db: Session, employee_id: int, year: int, month: int) -> dict:
    """Family P0.43 - Salary Days = the actual configured working days
    in the month, minus Applicable Leave Days. Only APPROVED leave
    counts, and only the portion of it that actually falls on a real
    working date within this month - a leave day that happens to land
    on an already-non-working Sunday/holiday does not additionally
    reduce salary days (it was never going to be paid working time
    anyway; subtracting it a second time would double-count).

    Returns the full breakdown the spec explicitly asks to keep
    distinct: calendar_days, working_days, leave_days, salary_days."""
    from app.modules.hr.models import Leave

    working_dates = get_working_dates(db, year, month)
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    leaves = db.query(Leave).filter(
        Leave.employee_id == employee_id,
        Leave.status == "Approved",
        Leave.start_date <= month_end,
        Leave.end_date >= month_start,
    ).all()

    leave_working_dates = set()
    for leave in leaves:
        overlap_start = max(leave.start_date.date(), month_start)
        overlap_end = min(leave.end_date.date(), month_end)
        current = overlap_start
        while current <= overlap_end:
            if current in working_dates:
                leave_working_dates.add(current)
            current += timedelta(days=1)

    working_days = len(working_dates)
    leave_days = len(leave_working_dates)
    return {
        "calendar_days": days_in_month,
        "working_days": working_days,
        "leave_days": leave_days,
        "salary_days": working_days - leave_days,
    }
