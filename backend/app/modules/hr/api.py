"""HR domain API routes: employees, attendance, leaves, salary
slips, salary advances, working calendar, holiday imports, and
exports. Combines the former employees.py, attendance.py, leaves.py,
salary_slips.py, salary_advances.py, working_calendar.py,
holiday_imports.py, and reports.py."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.platform.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.modules.hr.models import Employee
from app.modules.hr.schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeLifecycleItemUpdate
from app.modules.hr.services import (
    employee_overview, employee_calendar, employee_activity_timeline, employee_lifecycle,
    employee_relationships, employee_workload,
)
from app.platform.ids import generate_unique_code, generate_business_id
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from app.modules.hr.models import Attendance, Employee, OvertimeRequest
from app.modules.hr.schemas import (
    AttendanceCreate, AttendanceUpdate, AttendanceResponse, AttendanceOvertimeAction,
    OvertimeRequestCreate, OvertimeRequestUpdate, OvertimeRequestApprove, OvertimeRequestReject, OvertimeRequestResponse,
)
from app.modules.hr.services import (
    attendance_period_summary, attendance_day_detail, apply_overtime_hours,
    team_attendance_grid, attendance_exceptions, ATTENDANCE_DAY_VALUE,
)
from app.platform.ids import generate_business_id
from decimal import Decimal
from app.modules.hr.models import Leave
from app.modules.hr.schemas import LeaveCreate, LeaveUpdate, LeaveResponse
from datetime import datetime
import calendar
from app.modules.hr.models import SalarySlip, Attendance, Employee
from app.modules.hr.services import compute_working_days, compute_salary_days
from app.modules.hr.schemas import SalarySlipCreate, SalarySlipUpdate, SalarySlipResponse
from sqlalchemy.orm import Session, selectinload
from app.modules.hr.models import SalaryAdvance, Employee, SalarySlip
from app.modules.auth.auth import User
from app.modules.hr.schemas import SalaryAdvanceCreate, SalaryAdvanceApprove, SalaryAdvanceReject, SalaryAdvanceRecovery, SalaryAdvanceResponse
from app.modules.communications.services import NotificationService
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from app.modules.hr.models import WorkingCalendarSettings, CompanyHoliday
from app.modules.hr.schemas import WorkingWeekdayUpdate, WorkingWeekdayResponse, CompanyHolidayCreate, CompanyHolidayUpdate, CompanyHolidayResponse
from app.modules.hr.services import compute_working_days
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from fastapi.responses import StreamingResponse
from app.platform.config import settings
from app.platform.security import require_role
from app.modules.hr.models import CompanyHoliday
from app.modules.hr.services import (
    HolidayImportPreviewResponse, HolidayImportRowPreview,
    HolidayImportCommitRequest, HolidayImportCommitResult,
)
from app.modules.hr.services import build_import_template, parse_uploaded_workbook, validate_row
from typing import Optional
from app.platform.security import rate_limit
from app.modules.hr.models import SalarySlip, Employee, CompanyHoliday, Attendance, Leave
from app.shared import build_workbook, xlsx_response
from app.modules.hr.exports import generate_salary_slip_pdf


# --- employees.py ---
employees_router = APIRouter(prefix="/api/employees", tags=["employees"])


def _serialize_employees(employees, role: str, own_employee_id):
    """monthly_salary/daily_wage/pan/uan/bank details are confidential
    HR/payroll data (the same category as salary slips), not general
    directory info - genuinely nulled for every record except the
    requester's own, for non-privileged roles. Master accounts see
    everyone's.

    exit_reason (Family 137, section 13.9/13.16) joins this same list
    - a free-text reason someone left is exactly the kind of sensitive
    HR detail this rule already exists for. exit_date is left visible
    (the bare fact that/when someone left is ordinary directory
    information, unlike why)."""
    responses = [EmployeeResponse.model_validate(e) for e in employees]
    if role not in ("master",):
        for r in responses:
            if r.id != own_employee_id:
                r.monthly_salary = None
                r.daily_wage = None
                r.pan = None
                r.uan = None
                r.bank_name = None
                r.bank_account_number = None
                r.exit_reason = None
    return responses


def _serialize_employee(employee, role: str, own_employee_id):
    return _serialize_employees([employee], role, own_employee_id)[0]


def _require_own_or_master(auth: dict, employee_id: int) -> bool:
    """Family 137 (Employee 360, section 13.16) - "do not rely on
    frontend visibility as authorization; prevent users from accessing
    another employee's information unless explicitly authorized."
    Every Employee 360 read below is master-or-self, the same rule
    already enforced for attendance/leave lists (see list_attendance
    above). Returns whether the caller is a master (used by callers
    that additionally gate salary/cost figures to master-only even on
    an employee's own profile read)."""
    role = auth.get("role", "user")
    if role == "master":
        return True
    if auth.get("employee_id") == employee_id:
        return False
    raise HTTPException(status_code=403, detail="You can only view your own Employee 360 information.")


@employees_router.get("/", response_model=List[EmployeeResponse])
def list_employees(department: Optional[str] = Query(None), status: Optional[str] = Query(None),
                    search: Optional[str] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if status:
        query = query.filter(Employee.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like))
            | (Employee.designation.ilike(like)) | (Employee.phone.ilike(like)) | (Employee.email.ilike(like))
        )
    return _serialize_employees(query.order_by(Employee.name).all(), auth.get("role", "user"), auth.get("employee_id"))


@employees_router.post("/", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"employee_code"})
    for _ in range(5):
        code = generate_unique_code(db, Employee, "employee_code", "EMP-")
        employee = Employee(**payload, employee_code=code, business_id=generate_business_id(db))
        db.add(employee)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(employee)
        # Family 137 (Employee 360, section 13.10/13.16) - an employee
        # record being created is itself a consequential HR event and
        # the Employee Activity Timeline's first entry.
        log_action(db, request, user_id=auth.get("user_id"), action="create_employee", module_name="employees",
                   record_id=employee.id, new_value={"name": employee.name, "designation": employee.designation,
                                                       "department": employee.department, "status": employee.status})
        # Defect repair (P1-9): pre-seed the onboarding checklist here,
        # at the one moment an employee record is genuinely created -
        # this route already writes, so there is nothing to lose by
        # provisioning the checklist now, and it means the very first
        # time anyone opens this employee's 360 Overview or checklist
        # tab, real rows already exist rather than relying on a GET to
        # lazily create them (see employee_lifecycle's own docstring).
        employee_lifecycle(db, employee.id, "onboarding")
        return employee
    raise HTTPException(status_code=500, detail="Unable to generate a unique employee code, please try again")


@employees_router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _serialize_employee(employee, auth.get("role", "user"), auth.get("employee_id"))


@employees_router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    from app.platform.audit import serializable_fields

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    tracked_fields = ("designation", "department", "status", "monthly_salary", "manager")
    old_snapshot = serializable_fields(employee, tracked_fields)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(employee, field, value)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    new_snapshot = serializable_fields(employee, tracked_fields)
    if old_snapshot != new_snapshot:
        # Family 137 (Employee 360, section 13.10/13.16) - designation/
        # department/status/salary/manager are exactly the "designation
        # changes, salary changes" the Employee Activity Timeline spec
        # calls out; only logged when something tracked actually moved,
        # not on every no-op save.
        log_action(db, request, user_id=auth.get("user_id"), action="update_employee", module_name="employees",
                   record_id=employee.id, old_value=old_snapshot, new_value=new_snapshot)
    # Defect repair (P1-9): re-sync the checklist here, at an actual
    # write, rather than relying on the next GET to do it. designation/
    # manager (auto-derived onboarding items) and status (whether
    # offboarding should now be tracked at all) can all change via
    # this route - keeping the persisted checklist current the moment
    # they do (not just in the read-only summary computed for GETs)
    # means the checklist tab's own rows stay accurate without ever
    # depending on someone happening to open it.
    employee_lifecycle(db, employee.id, "onboarding")
    if employee.status == "Inactive":
        employee_lifecycle(db, employee.id, "offboarding")
    return employee


@employees_router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    from app.modules.hr.models import Attendance
    from app.modules.operations.models import DailyTask
    from app.modules.hr.models import Leave
    from app.modules.operations.models import ProductionJob
    from app.modules.hr.models import SalarySlip
    from app.modules.auth.auth import User

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Never hard-delete an employee with historical records - check
    # every table that actually has a foreign key to employees (found
    # by scanning every model, not assumed) before allowing this.
    reference_checks = [
        ("attendance records", db.query(Attendance).filter(Attendance.employee_id == employee_id).first()),
        ("daily tasks", db.query(DailyTask).filter(DailyTask.employee_id == employee_id).first()),
        ("leave records", db.query(Leave).filter(Leave.employee_id == employee_id).first()),
        ("production jobs", db.query(ProductionJob).filter(ProductionJob.employee_id == employee_id).first()),
        ("salary slips", db.query(SalarySlip).filter(SalarySlip.employee_id == employee_id).first()),
        ("a linked login account", db.query(User).filter(User.employee_id == employee_id).first()),
    ]
    blocking = [label for label, found in reference_checks if found is not None]
    if blocking:
        raise HTTPException(
            status_code=400,
            detail=f"This employee has {', '.join(blocking)} and cannot be permanently deleted. "
                   f"Set their status to Inactive instead to preserve historical records.",
        )

    employee_name = employee.name
    db.delete(employee)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_employee", module_name="employees",
               record_id=employee_id, old_value={"name": employee_name})


# --- Employee 360 / HR Command Center (Family 137, section 13) ---
# Every route below is read-only aggregation over existing HR/
# Productivity/Documents/audit data (see hr/services.py's own module
# docstring for the full reuse rationale), gated master-or-self via
# _require_own_or_master (section 13.16).

@employees_router.get("/{employee_id}/360-overview")
def get_employee_360_overview(employee_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    # _require_own_or_master already guarantees the caller is either a
    # master or this employee themselves (or raises 403) - both cases
    # get salary/cost figures on this employee's own overview, matching
    # _serialize_employees' existing rule that an employee's own salary
    # is never nulled out for them.
    _require_own_or_master(auth, employee_id)
    overview = employee_overview(
        db, employee_id, is_privileged=True, can_view_documents=auth.get("role", "user") == "master",
    )
    if overview is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return overview


@employees_router.get("/{employee_id}/workload")
def get_employee_workload(employee_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _require_own_or_master(auth, employee_id)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee_workload(db, employee_id)


@employees_router.get("/{employee_id}/relationships")
def get_employee_relationships(employee_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _require_own_or_master(auth, employee_id)
    relationships = employee_relationships(db, employee_id)
    if relationships is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return relationships


@employees_router.get("/{employee_id}/calendar")
def get_employee_calendar(employee_id: int, year: int = Query(...), month: int = Query(..., ge=1, le=12),
                           db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _require_own_or_master(auth, employee_id)
    result = employee_calendar(db, employee_id, year, month)
    if result is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result


@employees_router.get("/{employee_id}/activity-timeline")
def get_employee_activity_timeline(employee_id: int, limit: int = Query(200, ge=1, le=500),
                                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _require_own_or_master(auth, employee_id)
    timeline = employee_activity_timeline(
        db, employee_id, limit=limit, can_view_documents=auth.get("role", "user") == "master",
    )
    if timeline is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return timeline


@employees_router.get("/{employee_id}/lifecycle")
def get_employee_lifecycle(employee_id: int, phase: str = Query(..., pattern="^(onboarding|offboarding)$"),
                            db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _require_own_or_master(auth, employee_id)
    result = employee_lifecycle(db, employee_id, phase)
    if result is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result


@employees_router.put("/{employee_id}/lifecycle/{item_id}")
def update_employee_lifecycle_item(employee_id: int, item_id: int, data: EmployeeLifecycleItemUpdate,
                                    request: Request, db: Session = Depends(get_db),
                                    auth=Depends(require_role("master"))):
    """Toggling a checklist item is a master decision, same as every
    other consequential HR action in this module - not something an
    employee sets for themselves, and never something Cai (or any
    automation) sets on its own (section 13.13)."""
    from app.modules.hr.models import EmployeeLifecycleItem, ONBOARDING_AUTO_ITEMS

    item = db.query(EmployeeLifecycleItem).filter(
        EmployeeLifecycleItem.id == item_id, EmployeeLifecycleItem.employee_id == employee_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    if item.phase == "onboarding" and item.item_key in ONBOARDING_AUTO_ITEMS:
        raise HTTPException(
            status_code=400,
            detail="This item is derived automatically from existing records and cannot be toggled directly.",
        )
    old_value = {"is_complete": item.is_complete}
    item.is_complete = data.is_complete
    item.completed_date = datetime.utcnow() if data.is_complete else None
    item.completed_by = auth.get("email") if data.is_complete else None
    item.remarks = data.remarks
    db.add(item)
    db.commit()
    db.refresh(item)
    log_action(db, request, user_id=auth.get("user_id"), action="update_lifecycle_item", module_name="employees",
               record_id=employee_id, old_value=old_value,
               new_value={"is_complete": item.is_complete, "item_key": item.item_key, "phase": item.phase})
    return {
        "id": item.id, "item_key": item.item_key, "label": item.label, "is_complete": item.is_complete,
        "completed_date": item.completed_date.isoformat() if item.completed_date else None,
        "completed_by": item.completed_by, "remarks": item.remarks,
    }


# --- attendance.py ---
attendance_router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@attendance_router.get("/", response_model=List[AttendanceResponse])
def list_attendance(employee_id: Optional[int] = Query(None), date: Optional[datetime] = Query(None),
                     date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                     db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """date_from/date_to (Attendance & Overtime Command Center, spec
    section 12) is purely additive - the pre-existing single-`date`
    filter and the no-filter "everything" behaviour are both unchanged,
    this just adds a real date-range query so the new calendar/grid
    views never have to fetch a whole history client-side to filter it
    themselves."""
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
    if date_from:
        query = query.filter(Attendance.date >= date_from)
    if date_to:
        query = query.filter(Attendance.date <= date_to)
    return query.order_by(Attendance.date.desc()).all()


@attendance_router.post("/", response_model=AttendanceResponse, status_code=201)
def mark_attendance(data: AttendanceCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",) and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only mark attendance for yourself.")
    # Family P0.43 - overtime is a Master decision, never something an
    # employee can grant themselves by marking their own attendance
    # (spec: "employee must not be able to add overtime for themselves
    # without the required workflow"). Zero is always allowed (the
    # honest default for a normal day); any positive value requires
    # Master.
    if auth.get("role", "user") not in ("master",) and data.overtime_hours and data.overtime_hours > 0:
        raise HTTPException(status_code=403, detail="Only a Master user can record overtime hours.")

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


@attendance_router.put("/{attendance_id}", response_model=AttendanceResponse)
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


@attendance_router.post("/overtime", response_model=List[AttendanceResponse])
def manage_overtime(data: AttendanceOvertimeAction, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The 'Manage Overtime' action - Master-only, covers both single
    and multiple dates (a single date is just a one-item list). Never
    invents payable overtime from clock times/Sunday attendance/
    working-hours excess (see Attendance.overtime_hours's own column
    comment) - this is the ONLY path that changes it, and only because
    the Master explicitly called it.

    mode="add" (the default) is genuinely additive per-date - each
    selected date's own existing overtime_hours is increased by
    `hours` independently; an unselected date is never touched, and
    two dates with different existing values end up with different
    totals, not the same one (spec section 13's own worked example).
    mode="set" replaces each selected date's value outright instead.

    A date with no existing Attendance record for this employee gets
    a new one created (attendance_status defaults to "Present" - a
    bare overtime entry does not know or claim anything about the
    employee's regular-hours attendance that day, so it is deliberately
    not "Absent"/"Leave" either)."""
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Refactored (Attendance & Overtime Command Center) to call the
    # shared apply_overtime_hours - the exact same write this bulk
    # action always did, just extracted so it is no longer duplicated
    # between here and the new OvertimeRequest approval route below.
    updated_records = [apply_overtime_hours(db, data.employee_id, target_date, data.hours, mode=data.mode)
                        for target_date in data.dates]

    db.commit()
    for record in updated_records:
        db.refresh(record)
    return updated_records


@attendance_router.get("/period-summary")
def get_attendance_period_summary(employee_id: int = Query(...), start: datetime = Query(...), end: datetime = Query(...),
                                   db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The Attendance & Overtime Command Center's KPI strip + calendar
    call - master-or-self, same rule as every other per-employee read
    in this module."""
    _require_own_or_master(auth, employee_id)
    if end.date() < start.date():
        raise HTTPException(status_code=422, detail="end must not be before start")
    result = attendance_period_summary(db, employee_id, start.date(), end.date())
    if result is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result


@attendance_router.get("/day-detail")
def get_attendance_day_detail(employee_id: int = Query(...), date: datetime = Query(...),
                               db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The day-detail drawer's single call (spec section 4) - master-
    or-self."""
    _require_own_or_master(auth, employee_id)
    result = attendance_day_detail(db, employee_id, date.date())
    if result is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result


@attendance_router.get("/team-grid")
def get_team_attendance_grid(start: datetime = Query(...), end: datetime = Query(...),
                              department: Optional[str] = Query(None),
                              db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The Master team-grid view (spec section 7) - master-only, one
    call for every active employee across the range."""
    if end.date() < start.date():
        raise HTTPException(status_code=422, detail="end must not be before start")
    return team_attendance_grid(db, start.date(), end.date(), department)


@attendance_router.get("/exceptions")
def get_attendance_exceptions(employee_id: Optional[int] = Query(None), start: datetime = Query(...), end: datetime = Query(...),
                               db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The 'what needs attention' feed (spec section 8). An employee
    may only ask for their own; omitting employee_id is master-only
    (it means 'every active employee'), same master-or-self shape as
    every other read here."""
    role = auth.get("role", "user")
    if role != "master":
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own exceptions.")
        if not own_employee_id:
            return {"start_date": start.date().isoformat(), "end_date": end.date().isoformat(), "exceptions": []}
        employee_id = own_employee_id
    if end.date() < start.date():
        raise HTTPException(status_code=422, detail="end must not be before start")
    return attendance_exceptions(db, employee_id, start.date(), end.date())


# --- overtime_requests.py (Attendance & Overtime Command Center) ---
overtime_requests_router = APIRouter(prefix="/api/overtime-requests", tags=["overtime-requests"])


def _notify_overtime_decision(db, request: OvertimeRequest, decision: str) -> None:
    """Mirrors _notify_advance_decision below - the same best-effort,
    non-blocking notification pattern already established for salary
    advance decisions, reused rather than reinvented."""
    employee = request.employee
    if not employee:
        return
    recipient = db.query(User).filter(User.employee_id == employee.id).first()
    if decision == "approved":
        title = "Overtime request approved"
        message = f"Your overtime request for {request.date.strftime('%d %b %Y')} has been approved for {request.approved_hours}h."
    else:
        title = "Overtime request rejected"
        message = f"Your overtime request for {request.date.strftime('%d %b %Y')} has been rejected."
        if request.rejection_reason:
            message += f" Reason: {request.rejection_reason}"
    NotificationService.notify(
        db, notification_type="OVERTIME_REQUEST_DECISION", severity="INFO" if decision == "approved" else "WARNING",
        title=title, message=message,
        recipient_user_id=recipient.id if recipient else None,
        related_entity_type="overtime_request", related_entity_id=request.id,
        action_path="/attendance",
        recipient_email=employee.email if employee.email else None,
        email_subject=title, email_body=message,
    )


def _serialize_overtime_request(request: OvertimeRequest) -> OvertimeRequestResponse:
    response = OvertimeRequestResponse.model_validate(request, from_attributes=True)
    if request.employee:
        response.employee_name = request.employee.name
    return response


@overtime_requests_router.get("/", response_model=List[OvertimeRequestResponse])
def list_overtime_requests(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                            db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own overtime requests.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(OvertimeRequest)
    if employee_id:
        query = query.filter(OvertimeRequest.employee_id == employee_id)
    if status:
        query = query.filter(OvertimeRequest.status == status)
    return [_serialize_overtime_request(r) for r in query.order_by(OvertimeRequest.date.desc()).all()]


@overtime_requests_router.post("/", response_model=OvertimeRequestResponse, status_code=201)
def create_overtime_request(data: OvertimeRequestCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Created as Draft (spec: a real Draft/Submitted/Approved/Rejected
    workflow) - an employee requesting overtime for themselves, or a
    Master drafting one on anyone's behalf (mirrors
    request_salary_advance's own is_master-or-self shape)."""
    is_master = auth.get("role", "user") in ("master",)
    if not is_master and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only request overtime for yourself.")
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    creator = auth.get("username") or str(auth.get("user_id"))
    for _ in range(5):
        request = OvertimeRequest(
            business_id=generate_business_id(db), employee_id=data.employee_id, date=data.date,
            requested_hours=data.requested_hours, reason=data.reason, remarks=data.remarks,
            status="Draft", created_by=creator,
        )
        db.add(request)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(request)
        return _serialize_overtime_request(request)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


def _get_own_or_master_request(db: Session, request_id: int, auth: dict) -> OvertimeRequest:
    request = db.query(OvertimeRequest).filter(OvertimeRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    if auth.get("role", "user") not in ("master",) and request.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own overtime requests.")
    return request


@overtime_requests_router.put("/{request_id}", response_model=OvertimeRequestResponse)
def update_overtime_request(request_id: int, data: OvertimeRequestUpdate, db: Session = Depends(get_db),
                             auth=Depends(get_current_user)):
    request = _get_own_or_master_request(db, request_id, auth)
    if request.status != "Draft":
        raise HTTPException(status_code=409, detail=f"This request is {request.status.lower()} and can no longer be edited.")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(request, field, value)
    db.add(request)
    db.commit()
    db.refresh(request)
    return _serialize_overtime_request(request)


@overtime_requests_router.post("/{request_id}/submit", response_model=OvertimeRequestResponse)
def submit_overtime_request(request_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    request = _get_own_or_master_request(db, request_id, auth)
    if request.status != "Draft":
        raise HTTPException(status_code=409, detail=f"This request is already {request.status.lower()}.")
    request.status = "Submitted"
    request.submitted_at = datetime.utcnow()
    db.add(request)
    db.commit()
    db.refresh(request)
    return _serialize_overtime_request(request)


@overtime_requests_router.delete("/{request_id}", status_code=204)
def cancel_overtime_request(request_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Withdraw while still Draft - once Submitted it needs a Master
    decision (approve/reject), same "can't unilaterally undo a
    request once it's in the approval queue" principle as leaves."""
    request = _get_own_or_master_request(db, request_id, auth)
    if request.status != "Draft":
        raise HTTPException(status_code=409, detail=f"Only a Draft request can be cancelled (this one is {request.status.lower()}).")
    db.delete(request)
    db.commit()


@overtime_requests_router.put("/{request_id}/approve", response_model=OvertimeRequestResponse)
def approve_overtime_request(request_id: int, data: OvertimeRequestApprove, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """Master-only. Approving writes Attendance.overtime_hours through
    the SAME apply_overtime_hours the bulk 'Manage Overtime' action
    uses (mode="add" - an approval adds to whatever overtime that date
    already carries, it never silently overwrites a Master's earlier
    direct correction), so this authoritative figure is written by one
    function no matter which workflow triggered it."""
    request = db.query(OvertimeRequest).filter(OvertimeRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    if request.status != "Submitted":
        raise HTTPException(status_code=409, detail=f"Only a Submitted request can be approved (this one is {request.status.lower()}).")

    approved_hours = data.approved_hours if data.approved_hours is not None else request.requested_hours
    apply_overtime_hours(db, request.employee_id, request.date, approved_hours, mode="add")

    request.approved_hours = approved_hours
    request.approved_by = auth.get("username") or str(auth.get("user_id"))
    request.approval_date = datetime.utcnow()
    request.status = "Approved"
    if data.remarks:
        request.remarks = data.remarks
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_overtime_decision(db, request, decision="approved")
    return _serialize_overtime_request(request)


@overtime_requests_router.put("/{request_id}/reject", response_model=OvertimeRequestResponse)
def reject_overtime_request(request_id: int, data: OvertimeRequestReject, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    request = db.query(OvertimeRequest).filter(OvertimeRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    if request.status != "Submitted":
        raise HTTPException(status_code=409, detail=f"Only a Submitted request can be rejected (this one is {request.status.lower()}).")
    request.status = "Rejected"
    request.rejection_reason = data.rejection_reason
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_overtime_decision(db, request, decision="rejected")
    return _serialize_overtime_request(request)


# --- leaves.py ---
leaves_router = APIRouter(prefix="/api/leaves", tags=["leaves"])


def calculate_leave_days(start_date, end_date) -> Decimal:
    """Inclusive calendar-day count: From = To counts as 1 day, and
    From=11 Aug / To=13 Aug counts as 3 days. Computed from the date
    portion only, so a start/end that differ only in time-of-day (e.g.
    both submitted as midnight-UTC from a <input type="date">) still
    produce the correct whole-day count instead of drifting by a
    fraction of a day."""
    delta_days = (end_date.date() - start_date.date()).days + 1
    return Decimal(delta_days)


@leaves_router.get("/", response_model=List[LeaveResponse])
def list_leaves(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own leave records.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(Leave)
    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)
    if status:
        query = query.filter(Leave.status == status)
    return query.order_by(Leave.start_date.desc()).all()


@leaves_router.post("/", response_model=LeaveResponse, status_code=201)
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


@leaves_router.put("/{leave_id}", response_model=LeaveResponse)
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


# --- salary_slips.py ---
salary_slips_router = APIRouter(prefix="/api/salary-slips", tags=["salary-slips"])


def _compute_net(data) -> None:
    gross = data.basic + data.da + data.hra + data.overtime_amount
    # advance_deduction is never on SalarySlipCreate/Update - the only
    # way it becomes non-zero is the salary-advance recovery action
    # (Family P0.44), which sets it directly on the model and calls
    # this same function to recompute net_salary rather than
    # duplicating the arithmetic. getattr keeps this function safe to
    # call with either a Create/Update schema (no such field, so 0)
    # or the SQLAlchemy model itself (a real, possibly non-zero value).
    advance_deduction = getattr(data, "advance_deduction", None) or Decimal("0")
    deductions = data.pf_deduction + data.tds_deduction + data.other_deductions + advance_deduction
    return gross - deductions


@salary_slips_router.get("/attendance-summary")
def suggest_from_attendance(employee_id: int, month: str, year: str, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    """Suggested working_days/paid_days/overtime_amount derived from this
    employee's real Attendance records for the given month - the master
    reviews and can adjust every value before actually saving a salary
    slip. Never writes anything itself. Day-value rule is explicit, not
    hidden: Present = 1 day, Half Day = 0.5 day,
    Absent/Leave = 0 (unpaid unless the master adjusts). working_days
    and the overtime hourly rate both come from the actual configured
    working calendar for THIS specific month (weekends/holidays/special
    working days), never a fixed assumption - a different month can and
    will produce a different total."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        period_start = datetime.strptime(f"{month} {year}", "%B %Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August', and year must be 4 digits")
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)

    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= period_start, Attendance.date <= period_end,
    ).all()

    working_days_this_month = compute_working_days(db, period_start.year, period_start.month)
    # Family P0.43's own explicit formula (Monday-Saturday working
    # days minus APPROVED leave) - a theoretical full-pay day count,
    # distinct from suggested_paid_days below (which reflects actual
    # recorded attendance and can differ, e.g. an unmarked absence
    # with no formal Leave record behind it). Both are given so the
    # Master can see and reconcile the difference, not one silently
    # replacing the other.
    salary_days_breakdown = compute_salary_days(db, employee_id, period_start.year, period_start.month)

    # Defect repair: this used to hardcode its own copy of the
    # Present=1/Half Day=0.5/Absent=0/Leave=0 day-value table. Now
    # reuses the one authoritative ATTENDANCE_DAY_VALUE constant
    # (hr/services.py) that attendance_period_summary/team_attendance_grid
    # and get_payroll_summary's own callers already use, so this rule
    # is never defined twice and cannot silently drift.
    paid_days = sum(ATTENDANCE_DAY_VALUE.get(r.attendance_status, 0) for r in records)
    total_overtime_hours = sum(r.overtime_hours for r in records)
    standard_hours_per_day = float(records[0].standard_hours) if records else 8
    daily_rate_this_month = (float(employee.monthly_salary or 0) / working_days_this_month) if working_days_this_month else 0
    hourly_rate = daily_rate_this_month / standard_hours_per_day if standard_hours_per_day else 0
    overtime_amount = round(total_overtime_hours * hourly_rate, 2)

    return {
        "employee_id": employee_id,
        "records_found": len(records),
        "suggested_working_days": working_days_this_month,
        "suggested_paid_days": paid_days,
        "total_overtime_hours": round(total_overtime_hours, 2),
        "suggested_overtime_amount": overtime_amount,
        "calendar_days": salary_days_breakdown["calendar_days"],
        "leave_days": salary_days_breakdown["leave_days"],
        "salary_days": salary_days_breakdown["salary_days"],
        "note": "Derived from Attendance records and the configured working calendar for this period - review before saving.",
    }


@salary_slips_router.get("/payroll-summary")
def payroll_summary(month: str, year: str, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family P0.43 - pure aggregation over SalarySlip.status and
    SalaryAdvance (see hr/payroll_service.py) - not a second payroll
    engine. Master-only: this is company-wide financial/payroll
    information."""
    from app.modules.hr.services import get_payroll_summary, get_salary_advance_summary
    return {
        **get_payroll_summary(db, month, year),
        "salary_advances": get_salary_advance_summary(db),
    }


@salary_slips_router.get("/", response_model=List[SalarySlipResponse])
def list_salary_slips(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    return query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()


@salary_slips_router.post("/", response_model=SalarySlipResponse, status_code=201)
def create_salary_slip(data: SalarySlipCreate, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        period_start = datetime.strptime(f"{data.month} {data.year}", "%B %Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August', and year must be 4 digits")

    if employee.joining_date:
        joining_period = employee.joining_date.replace(day=1)
        if period_start < joining_period:
            raise HTTPException(
                status_code=400,
                detail="Salary slip cannot be generated before the employee's joining date.",
            )

    existing = db.query(SalarySlip).filter(
        SalarySlip.employee_id == data.employee_id, SalarySlip.month == data.month, SalarySlip.year == data.year,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Salary slip for this employee/month/year already exists")

    for _ in range(5):
        net_salary = _compute_net(data)
        slip = SalarySlip(**data.dict(), net_salary=net_salary, business_id=generate_business_id(db))
        db.add(slip)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(slip)
        log_action(db, request, user_id=auth.get("user_id"), action="create_salary_slip", module_name="salary_slips",
                   record_id=slip.id, new_value={
                       "employee_id": slip.employee_id, "month": slip.month, "year": slip.year,
                       "net_salary": float(net_salary),
                   })
        return slip
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@salary_slips_router.get("/{slip_id}", response_model=SalarySlipResponse)
def get_salary_slip(slip_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    if auth.get("role", "user") not in ("master",) and slip.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
    return slip


@salary_slips_router.put("/{slip_id}", response_model=SalarySlipResponse)
def update_salary_slip(slip_id: int, data: SalarySlipUpdate, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    updates = data.dict(exclude_unset=True)
    new_working_days = updates.get("working_days", slip.working_days)
    new_paid_days = updates.get("paid_days", slip.paid_days)
    if new_paid_days > new_working_days:
        raise HTTPException(status_code=400, detail="paid_days cannot exceed working_days")

    def _serializable(field):
        value = getattr(slip, field)
        return float(value) if isinstance(value, (int, float, Decimal)) else value

    old_value = {field: _serializable(field) for field in updates}
    for field, value in updates.items():
        setattr(slip, field, value)
    slip.net_salary = _compute_net(slip)
    db.add(slip)
    db.commit()
    db.refresh(slip)
    new_value = {field: _serializable(field) for field in updates}
    log_action(db, request, user_id=auth.get("user_id"), action="update_salary_slip", module_name="salary_slips",
               record_id=slip.id, old_value=old_value, new_value=new_value)
    return slip


# --- salary_advances.py ---
"""Family P0.44 - Salary Advance Management API. The complete workflow
(spec section 5): Employee/Master request -> Master approve/reject ->
recovery against real SalarySlips. Recovery reuses
salary_slips.py's own _compute_net (imported, not reimplemented) so
net_salary is never calculated two different ways."""

salary_advances_router = APIRouter(prefix="/api/salary-advances", tags=["salary-advances"])


def _notify_advance_decision(db, advance: SalaryAdvance, decision: str) -> None:
    """One authoritative call into the same notify() every other
    module uses (in-app + email in one place, a failed email never
    corrupting the advance record itself - see notify()'s own
    docstring). Silently does nothing if this employee has no linked
    login account or no email on file - the decision itself is still
    saved regardless; this is a best-effort courtesy notification, not
    part of the approval/rejection's own correctness."""
    employee = advance.employee
    if not employee:
        return
    recipient = db.query(User).filter(User.employee_id == employee.id).first()
    if decision == "approved":
        title = "Salary advance approved"
        message = f"Your salary advance request has been approved for {advance.approved_amount}."
    else:
        title = "Salary advance rejected"
        message = "Your salary advance request has been rejected."
        if advance.rejection_reason:
            message += f" Reason: {advance.rejection_reason}"
    NotificationService.notify(
        db, notification_type="SALARY_ADVANCE_DECISION", severity="INFO" if decision == "approved" else "WARNING",
        title=title, message=message,
        recipient_user_id=recipient.id if recipient else None,
        related_entity_type="salary_advance", related_entity_id=advance.id,
        action_path="/salary-advances",
        recipient_email=employee.email if employee.email else None,
        email_subject=title, email_body=message,
    )


def _serialize(advance: SalaryAdvance) -> SalaryAdvanceResponse:
    response = SalaryAdvanceResponse.model_validate(advance)
    if advance.employee:
        response.employee_name = advance.employee.name
    return response


@salary_advances_router.get("/", response_model=List[SalaryAdvanceResponse])
def list_salary_advances(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                          db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Employee sees only their own (spec section 6) - identical IDOR
    pattern to leaves.py/attendance.py: a non-master querying someone
    else's employee_id is rejected outright, not silently redirected
    to their own, so a probing request gets a clear 403 rather than a
    misleadingly-successful-looking empty/own result."""
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own salary advance requests.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(SalaryAdvance).options(selectinload(SalaryAdvance.employee))
    if employee_id:
        query = query.filter(SalaryAdvance.employee_id == employee_id)
    if status:
        query = query.filter(SalaryAdvance.status == status)
    rows = query.order_by(SalaryAdvance.request_date.desc()).all()
    return [_serialize(r) for r in rows]


@salary_advances_router.post("/", response_model=SalaryAdvanceResponse, status_code=201)
def request_salary_advance(data: SalaryAdvanceCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Covers both the employee's own request and the Master
    direct-advance workflow (spec section 8) - an employee requesting
    for anyone but themselves is rejected exactly like leaves.py's
    equivalent check; a Master may create one for any valid employee."""
    is_master = auth.get("role", "user") in ("master",)
    if not is_master and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only request a salary advance for yourself.")

    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    creator = auth.get("username") or str(auth.get("user_id"))
    for _ in range(5):
        advance = SalaryAdvance(
            business_id=generate_business_id(db), employee_id=data.employee_id,
            requested_amount=data.requested_amount, request_date=data.request_date,
            reason=data.reason, remarks=data.remarks, status="Pending", recovered_amount=0,
            created_by=creator,
        )
        db.add(advance)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(advance)
        return _serialize(advance)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@salary_advances_router.get("/{advance_id}", response_model=SalaryAdvanceResponse)
def get_salary_advance(advance_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    advance = db.query(SalaryAdvance).options(selectinload(SalaryAdvance.employee)).filter(SalaryAdvance.id == advance_id).first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if auth.get("role", "user") not in ("master",) and advance.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary advance requests.")
    return _serialize(advance)


@salary_advances_router.put("/{advance_id}/approve", response_model=SalaryAdvanceResponse)
def approve_salary_advance(advance_id: int, data: SalaryAdvanceApprove,
                            db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Only MASTER (spec section 7). approved_amount defaults to the
    requested amount if not given; requested_amount itself is never
    touched (spec: "Requested Amount remains historical")."""
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Pending":
        raise HTTPException(status_code=409, detail=f"This advance is already {advance.status.lower()} - cannot approve it again.")

    advance.approved_amount = data.approved_amount if data.approved_amount is not None else advance.requested_amount
    advance.approved_by = auth.get("username") or str(auth.get("user_id"))
    from datetime import datetime
    advance.approval_date = datetime.utcnow()
    advance.recovery_month = data.recovery_month
    advance.recovery_year = data.recovery_year
    advance.status = "Approved"
    if data.remarks:
        advance.remarks = data.remarks
    db.add(advance)
    db.commit()
    db.refresh(advance)
    _notify_advance_decision(db, advance, decision="approved")
    return _serialize(advance)


@salary_advances_router.put("/{advance_id}/reject", response_model=SalaryAdvanceResponse)
def reject_salary_advance(advance_id: int, data: SalaryAdvanceReject,
                           db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Pending":
        raise HTTPException(status_code=409, detail=f"This advance is already {advance.status.lower()} - cannot reject it again.")

    advance.status = "Rejected"
    advance.rejection_reason = data.rejection_reason
    db.add(advance)
    db.commit()
    db.refresh(advance)
    _notify_advance_decision(db, advance, decision="rejected")
    return _serialize(advance)


@salary_advances_router.post("/{advance_id}/recover", response_model=SalaryAdvanceResponse)
def record_salary_advance_recovery(advance_id: int, data: SalaryAdvanceRecovery,
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Recovery against one real, existing SalarySlip for this
    employee/month - never a bare number typed here with nothing
    behind it (spec section 10's "must use the authoritative payroll
    calculation"). Row-locks both the advance and the slip to prevent
    a concurrent double-recovery from either passing its own
    outstanding-balance check against stale data."""
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Approved":
        raise HTTPException(status_code=409, detail="Only an approved advance can have recovery recorded against it.")

    outstanding = advance.outstanding_amount
    if data.amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot recover {data.amount} - only {outstanding} remains outstanding on this advance.",
        )

    slip = (
        db.query(SalarySlip)
        .filter(SalarySlip.employee_id == advance.employee_id, SalarySlip.month == data.month, SalarySlip.year == data.year)
        .with_for_update().first()
    )
    if not slip:
        raise HTTPException(
            status_code=404,
            detail=f"No salary slip exists for this employee for {data.month} {data.year} - create it before recording recovery against it.",
        )

    advance.recovered_amount = (advance.recovered_amount or 0) + data.amount
    slip.advance_deduction = (slip.advance_deduction or 0) + data.amount
    slip.net_salary = _compute_net(slip)
    db.add(advance)
    db.add(slip)
    db.commit()
    db.refresh(advance)
    return _serialize(advance)


# --- working_calendar.py ---
working_calendar_router = APIRouter(prefix="/api/working-calendar", tags=["working-calendar"])


@working_calendar_router.get("/weekdays", response_model=List[WorkingWeekdayResponse])
def list_weekdays(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Readable by any authenticated user (the calendar affects
    everyone's attendance/payroll context), editable by master only."""
    return db.query(WorkingCalendarSettings).order_by(WorkingCalendarSettings.id).all()


@working_calendar_router.put("/weekdays/{weekday_id}", response_model=WorkingWeekdayResponse)
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


@working_calendar_router.get("/holidays", response_model=List[CompanyHolidayResponse])
def list_holidays(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(CompanyHoliday).order_by(CompanyHoliday.date).all()


@working_calendar_router.post("/holidays", response_model=CompanyHolidayResponse, status_code=201)
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


@working_calendar_router.put("/holidays/{holiday_id}", response_model=CompanyHolidayResponse)
def update_holiday(holiday_id: int, data: CompanyHolidayUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    holiday = db.query(CompanyHoliday).filter(CompanyHoliday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    update_data = data.dict(exclude_unset=True)
    if "date" in update_data and update_data["date"] != holiday.date:
        collision = db.query(CompanyHoliday).filter(
            CompanyHoliday.date == update_data["date"], CompanyHoliday.id != holiday_id,
        ).first()
        if collision:
            raise HTTPException(status_code=400, detail="A calendar override already exists for this date")

    old_value = {"date": str(holiday.date), "name": holiday.name, "is_working": holiday.is_working}
    for field, value in update_data.items():
        setattr(holiday, field, value)
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    log_action(db, request, user_id=auth.get("user_id"), action="update_company_holiday",
               module_name="working_calendar", record_id=holiday.id,
               old_value=old_value, new_value={"date": str(holiday.date), "name": holiday.name, "is_working": holiday.is_working})
    return holiday


@working_calendar_router.delete("/holidays/{holiday_id}", status_code=204)
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


@working_calendar_router.get("/working-days")
def get_working_days(year: int, month: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Read-only: the computed working-day count for a given month,
    using the current calendar configuration. Any authenticated user
    can check this (it's not sensitive), matching how the weekday
    list itself is also readable by anyone."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="month must be between 1 and 12")
    return {"year": year, "month": month, "working_days": compute_working_days(db, year, month)}


# --- holiday_imports.py ---
holiday_imports_router = APIRouter(prefix="/api/holiday-imports", tags=["holiday-imports"])


@holiday_imports_router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Company_Holiday_Import_Template.xlsx"},
    )


@holiday_imports_router.post("/preview", response_model=HolidayImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file only - never writes to
    the database. A date that already has a holiday is flagged as a
    duplicate (not an error) so the commit step can offer update-or-skip,
    supporting the Export -> Edit -> Import workflow."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    allowed_mime_types = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
            )
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    existing_dates = {h.date for h in db.query(CompanyHoliday.date).all()}
    seen_dates_in_file = set()

    preview_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    for idx, row in enumerate(raw_rows, start=1):
        parsed, errors = validate_row(row, existing_dates, seen_dates_in_file)
        if errors:
            error_count += 1
        elif parsed["is_duplicate"]:
            duplicate_count += 1
        else:
            new_count += 1
        preview_rows.append(HolidayImportRowPreview(row_number=idx, **parsed, errors=errors))

    return HolidayImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count,
        duplicate_rows=duplicate_count, error_rows=error_count, rows=preview_rows,
    )


@holiday_imports_router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the logic /preview
    uses) and returns a real .xlsx listing only the rejected rows, each
    with its original row number and the specific reason(s) it was
    rejected - matching the established pattern from client_imports.py."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.")
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    existing_dates = {h.date for h in db.query(CompanyHoliday.date).all()}
    seen_dates_in_file = set()
    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        parsed, errors = validate_row(row, existing_dates, seen_dates_in_file)
        if errors:
            error_rows.append({
                "row": idx, "date": str(row.get("Date *") or ""), "name": row.get("Holiday Name *") or "",
                "type": row.get("Type *") or "", "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    from fastapi.responses import StreamingResponse
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Holiday Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "date", "name", "type", "reason"],
        "headers": ["Excel Row", "Date", "Holiday Name", "Type", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Holiday_Import_Errors.xlsx"},
    )


@holiday_imports_router.post("/commit", response_model=HolidayImportCommitResult)
def commit_import(data: HolidayImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """A row whose date already exists is only ever touched if the
    caller explicitly set overwrite_existing (the user confirmed this
    during preview) - otherwise it's safely skipped, never silently
    duplicated or silently overwritten."""
    created = 0
    updated = 0
    skipped = 0
    error_message = None

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        try:
            existing = db.query(CompanyHoliday).filter(CompanyHoliday.date == row.date).first()
            if existing:
                if not row.overwrite_existing:
                    skipped += 1
                    continue
                existing.name = row.name
                existing.is_working = row.is_working
                existing.remarks = row.remarks
                db.add(existing)
                db.commit()
                updated += 1
            else:
                holiday = CompanyHoliday(date=row.date, name=row.name, is_working=row.is_working, remarks=row.remarks)
                db.add(holiday)
                db.commit()
                created += 1
        except Exception as e:
            db.rollback()
            error_message = f"Stopped at row {i + 1}: {str(e)}"
            break

    log_action(
        db, request, user_id=auth.get("user_id"), action="import_company_holidays", module_name="working_calendar",
        new_value={"created": created, "updated": updated, "skipped": skipped},
    )

    return HolidayImportCommitResult(created=created, updated=updated, skipped=skipped, error=error_message)


# --- reports.py ---
"""HR-domain report exports: employees, attendance, leaves, payroll,
salary slip PDF, and company holidays. Split out of the former
monolithic reports.py - see modules/inventory/api/reports.py's docstring for
why."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/employees.xlsx")
def export_employees(
    search: Optional[str] = Query(None), department: Optional[str] = Query(None),
    status: Optional[str] = Query(None), db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Employee Directory export (P5) - mirrors GET /api/employees/'s
    search/department/status filters."""
    query = db.query(Employee)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like))
            | (Employee.designation.ilike(like)) | (Employee.phone.ilike(like)) | (Employee.email.ilike(like))
        )
        filters_applied.append(f'Search: "{search}"')
    if department:
        query = query.filter(Employee.department == department)
        filters_applied.append(f"Department: {department}")
    if status:
        query = query.filter(Employee.status == status)
        filters_applied.append(f"Status: {status}")

    employees = query.order_by(Employee.name).all()
    rows = [{
        "employee_id": e.business_id or "", "name": e.name, "designation": e.designation or "",
        "department": e.department or "", "phone": e.phone or "", "email": e.email or "",
        "joining_date": e.joining_date.strftime("%d-%m-%Y") if e.joining_date else "",
        "status": e.status, "manager": e.manager or "",
    } for e in employees]
    columns = ["employee_id", "name", "designation", "department", "phone", "email",
               "joining_date", "status", "manager"]
    headers = ["Employee ID", "Employee Name", "Designation", "Department", "Phone", "Email",
               "Joining Date", "Employment Status", "Manager/Supervisor"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Employees", str(len(employees)))]
    active_count = sum(1 for e in employees if e.status == "Active")
    summary.append(("Active", str(active_count)))
    summary.append(("Inactive/Other", str(len(employees) - active_count)))

    buffer = build_workbook([{
        "sheet_name": "Employees", "title": "EMPLOYEE DIRECTORY",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": summary,
    }])
    filename = f"employee_directory_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/attendance.xlsx")
def export_attendance(
    employee_id: Optional[int] = Query(None), month: Optional[str] = Query(None), year: Optional[str] = Query(None),
    attendance_status: Optional[str] = Query(None), overtime_only: bool = Query(False),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Attendance export - overtime_only covers "Overtime Excel" as a
    filtered view of the same data rather than a separate endpoint,
    since it's the same model with the same columns, just narrowed to
    records where overtime_hours > 0."""
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own attendance records.")
        if not own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own attendance records.")
        employee_id = own_employee_id

    query = db.query(Attendance).options(selectinload(Attendance.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if month and year:
        try:
            period_start = datetime.strptime(f"{month} {year}", "%B %Y")
            last_day = calendar.monthrange(period_start.year, period_start.month)[1]
            period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)
            query = query.filter(Attendance.date >= period_start, Attendance.date <= period_end)
            filters_applied.append(f"Period: {month} {year}")
        except ValueError:
            raise HTTPException(status_code=400, detail="month must be a full month name, e.g. 'August'")
    if attendance_status:
        query = query.filter(Attendance.attendance_status == attendance_status)
        filters_applied.append(f"Status: {attendance_status}")

    records = query.order_by(Attendance.date.desc()).all()
    if overtime_only:
        records = [r for r in records if r.overtime_hours > 0]
        filters_applied.append("Overtime only")

    rows = [{
        "attendance_id": r.business_id or "", "date": r.date.strftime("%d-%m-%Y") if r.date else "",
        "employee": r.employee.name if r.employee else "",
        "in_time": r.in_time.strftime("%H:%M") if r.in_time else "",
        "out_time": r.out_time.strftime("%H:%M") if r.out_time else "",
        "standard_hours": float(r.standard_hours or 0), "working_hours": r.working_hours,
        "overtime_hours": r.overtime_hours, "status": r.attendance_status, "remarks": r.remarks or "",
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Records", str(len(records))),
        ("Total Working Hours", f"{sum(r.working_hours for r in records):.2f}"),
        ("Total Overtime Hours", f"{sum(r.overtime_hours for r in records):.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Overtime" if overtime_only else "Attendance",
        "title": "OVERTIME REPORT" if overtime_only else "ATTENDANCE REPORT",
        "columns": ["attendance_id", "date", "employee", "in_time", "out_time", "standard_hours",
                    "working_hours", "overtime_hours", "status", "remarks"],
        "headers": ["Attendance ID", "Date", "Employee", "In Time", "Out Time", "Standard Hours",
                    "Working Hours", "Overtime Hours", "Status", "Remarks"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"{'overtime' if overtime_only else 'attendance'}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/leaves.xlsx")
def export_leaves(
    employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own leave records.")
        if not own_employee_id:
            raise HTTPException(status_code=403, detail="You can only export your own leave records.")
        employee_id = own_employee_id

    query = db.query(Leave).options(selectinload(Leave.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(Leave.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if status:
        query = query.filter(Leave.status == status)
        filters_applied.append(f"Status: {status}")

    records = query.order_by(Leave.start_date.desc()).all()
    rows = [{
        "leave_id": r.business_id or "", "employee": r.employee.name if r.employee else "",
        "leave_type": r.leave_type, "start_date": r.start_date.strftime("%d-%m-%Y") if r.start_date else "",
        "end_date": r.end_date.strftime("%d-%m-%Y") if r.end_date else "", "days": float(r.days or 0),
        "status": r.status, "approved_by": r.approved_by or "", "reason": r.reason or "",
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Requests", str(len(records))),
        ("Total Days", f"{sum(float(r.days or 0) for r in records):.1f}"),
        ("Approved", str(sum(1 for r in records if r.status == "Approved"))),
    ]

    buffer = build_workbook([{
        "sheet_name": "Leave", "title": "LEAVE REPORT",
        "columns": ["leave_id", "employee", "leave_type", "start_date", "end_date", "days", "status", "approved_by", "reason"],
        "headers": ["Leave ID", "Employee", "Type", "Start Date", "End Date", "Days", "Status", "Approved By", "Reason"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"leaves_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/payroll.xlsx")
def export_payroll(
    employee_id: Optional[int] = Query(None), month: Optional[str] = Query(None), year: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Master-only, matching the same require_role("master") gate the
    salary-slip routes themselves already use - this must never be
    reachable by a direct API call from a non-master session, not just
    hidden from the UI."""
    query = db.query(SalarySlip).options(selectinload(SalarySlip.employee))
    filters_applied = []
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if month:
        query = query.filter(SalarySlip.month == month)
        filters_applied.append(f"Month: {month}")
    if year:
        query = query.filter(SalarySlip.year == year)
        filters_applied.append(f"Year: {year}")

    records = query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    rows = [{
        "slip_id": r.business_id or "", "employee": r.employee.name if r.employee else "",
        "month": r.month, "year": r.year, "working_days": float(r.working_days or 0),
        "paid_days": float(r.paid_days or 0), "basic": float(r.basic or 0), "da": float(r.da or 0),
        "hra": float(r.hra or 0), "overtime_amount": float(r.overtime_amount or 0),
        "pf_deduction": float(r.pf_deduction or 0), "tds_deduction": float(r.tds_deduction or 0),
        "other_deductions": float(r.other_deductions or 0), "net_salary": float(r.net_salary or 0),
        "status": r.status,
    } for r in records]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Slips", str(len(records))),
        ("Total Net Payout", f"Rs {sum(float(r.net_salary or 0) for r in records):,.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Payroll", "title": "PAYROLL REPORT",
        "columns": ["slip_id", "employee", "month", "year", "working_days", "paid_days", "basic", "da", "hra",
                    "overtime_amount", "pf_deduction", "tds_deduction", "other_deductions", "net_salary", "status"],
        "headers": ["Slip ID", "Employee", "Month", "Year", "Working Days", "Paid Days", "Basic", "DA", "HRA",
                    "Overtime", "PF Deduction", "TDS Deduction", "Other Deductions", "Net Salary", "Status"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"payroll_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/salary-slips/{slip_id}.pdf")
def export_salary_slip_pdf(slip_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    if auth.get("role", "user") not in ("master",) and slip.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary slips.")
    buffer = generate_salary_slip_pdf(slip, db)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="salary-slip-{slip.month}-{slip.year}.pdf"', "Cache-Control": "no-store, private"},
    )


@reports_router.get("/company-holidays.xlsx")
def export_company_holidays(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The actual stored Company Holiday records, in a
    format that round-trips back through the Holiday Import:
    headers alias to the same import columns, Date is written as
    %Y-%m-%d specifically (the one format the import parser accepts -
    this file's other exports use %d-%m-%Y, which would NOT re-import
    correctly), and Type is the same readable 'Holiday'/'Special
    Working Day' text the import expects, not the raw is_working
    boolean. Master can Export -> edit in Excel -> Import to maintain
    holidays, per the spec's own intended workflow."""
    holidays = db.query(CompanyHoliday).order_by(CompanyHoliday.date).all()
    rows = [{
        "date": h.date.strftime("%Y-%m-%d"),
        "name": h.name,
        "type": "Special Working Day" if h.is_working else "Holiday",
        "remarks": h.remarks or "",
    } for h in holidays]
    columns = ["date", "name", "type", "remarks"]
    headers = ["Date", "Holiday Name", "Type", "Remarks"]
    buffer = build_workbook([{"sheet_name": "Company Holidays", "title": "COMPANY HOLIDAYS",
                               "columns": columns, "headers": headers, "rows": rows,
                               "summary": [("Total Holidays", str(len(holidays)))]}])
    return xlsx_response(buffer, f"company-holidays_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")
