"""HR services: chatbot-tool routing (employee/task/leave/salary
queries), payroll summaries (salary advance/overtime), working-
calendar computation, and company-holiday Excel import. Combines the
former services.py, payroll_service.py, working_calendar_service.py,
imports/holiday_schemas.py, and imports/holiday_import.py."""
import re
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.modules.hr.models import Employee, Leave
from app.modules.operations.models import DailyTask
from app.modules.auth.auth import User
from app.modules.communications.services import NotificationService
from app.platform.ids import generate_unique_code, generate_business_id
from app.modules.ai.contracts import ChatContext, ProposedAction
from decimal import Decimal
from app.modules.hr.models import Employee, SalarySlip, SalaryAdvance
import calendar
from datetime import date, timedelta
from app.modules.hr.models import WorkingCalendarSettings, CompanyHoliday
from typing import List, Optional
from pydantic import BaseModel
from io import BytesIO
import openpyxl
from app.shared_imports import enforce_workbook_row_limit
from openpyxl import Workbook
from app.shared import write_sheet, write_instructions_sheet


# --- services.py ---
"""Chatbot HR-domain query/action handlers - employee/leave/task/
salary lookups, employee-add and task-assign/complete actions, and
the shared employee-name resolution helpers. Split out of the former
monolithic chat_service.py - see chat_inventory.py's docstring for
why."""

ASSIGN_TASK_PATTERN = re.compile(r"assign (.+?) to ([a-z]+)")


def _resolve_employee_by_name(db: Session, name: str) -> Tuple[Optional[Employee], List[Employee]]:
    """Never silently picks the first partial
    name match. Returns (employee, []) for exactly one match,
    (None, matches) when the name is genuinely ambiguous (so the
    caller can ask which one), or (None, []) when nothing matches at
    all. The partial, case-insensitive search itself is unchanged and
    correct ("Ravi" genuinely should find both "Ravi Kumar" and "Ravi
    Sharma") - what changes is refusing to guess when more than one
    real match comes back."""
    matches = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).all()
    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        return None, matches
    return None, []


def _employee_ambiguity_message(name: str, matches: List[Employee]) -> str:
    names = ", ".join(sorted(e.name for e in matches))
    return f"I found multiple employees matching \"{name}\": {names}. Which one did you mean?"


def _complete_task_action(db: Session, user_role: str, current_employee_id: Optional[int],
                           context: Optional[ChatContext]):
    """"Mark this done" - resolves "this task" from page context
    (record_type/record_id), enforces the exact same ownership rule
    as PUT /api/daily-tasks/{id}/complete-and-assign-next, and
    performs the real update - never a second, chat-only version of
    this logic. Simple task actions may execute directly without a
    confirmation step, unlike financial actions such as payments."""
    if not context:
        return "I'm not sure which task you mean - open the task first, then ask me to mark it done.", [], []
    record_type, record_id = context.resolved()
    if record_type != "task" or not record_id:
        return "I'm not sure which task you mean - open the task first, then ask me to mark it done.", [], []

    task = db.query(DailyTask).filter(DailyTask.id == record_id).with_for_update().first()
    if not task:
        return "I couldn't find that task.", [], []
    if user_role not in ("master",) and task.employee_id != current_employee_id:
        return "You can only complete your own tasks.", [], []

    from app.modules.operations.api_operations import apply_task_completion
    apply_task_completion(task)
    db.add(task)
    db.commit()
    db.refresh(task)

    recipient = db.query(User).filter(User.employee_id == task.employee_id).first()
    if recipient:
        NotificationService.notify(
            db, notification_type="TASK_STATUS_CHANGED", severity="INFO",
            title="Task status: DONE", message=task.task_description,
            recipient_user_id=recipient.id, related_entity_type="task",
            related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
            dedup_key=f"task-status-{task.id}-DONE",
        )
    return f"Marked \"{task.task_description}\" as done.", [], [{
        "type": "Task", "label": task.task_description, "sublabel": "DONE", "path": f"/daily-tasks/{task.id}",
    }]


def _assign_task_action(m: str, db: Session, context: Optional[ChatContext], user_role: str):
    """"Assign wardrobe cutting to Pankaj" - creates a real task via
    the same fields/notification the POST /api/daily-tasks/ endpoint
    uses, not a second creation path. Master-only, matching that
    real endpoint exactly - task creation was
    previously, incorrectly treated as open to any role here; the
    real endpoint has always been require_role("master")."""
    match = ASSIGN_TASK_PATTERN.search(m)
    if not match:
        return None
    if user_role not in ("master",):
        return "Creating and assigning tasks requires a master account.", [], []
    task_text = re.sub(r"^(the|a|an)\s+", "", match.group(1).strip())
    name = match.group(2).strip()

    employee, ambiguous_matches = _resolve_employee_by_name(db, name)
    if ambiguous_matches:
        return _employee_ambiguity_message(name, ambiguous_matches), [], []
    if not employee:
        return f"I couldn't find an employee matching \"{name}\".", [], []

    order_id = context.order_id if context else None
    for _ in range(5):
        code = generate_unique_code(db, DailyTask, "task_code", "TSK-")
        task = DailyTask(
            task_code=code, business_id=generate_business_id(db), date=datetime.utcnow(),
            employee_id=employee.id, order_id=order_id, task_description=task_text.capitalize(),
            status="TO DO",
        )
        db.add(task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(task)
        recipient = db.query(User).filter(User.employee_id == employee.id).first()
        email_subject = f"Task Assigned: {task.task_code}"
        email_body = f"Task ID: {task.task_code}\nWork: {task.task_description}\nStatus: {task.status}\n\nOpen this task: /daily-tasks/{task.id}"
        if recipient:
            NotificationService.notify(
                db, notification_type="TASK_ASSIGNED", severity="INFO",
                title="New task assigned", message=task.task_description,
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                recipient_email=employee.email, email_subject=email_subject, email_body=email_body,
            )
        elif employee.email:
            try:
                from app.modules.communications.services import EmailService
                EmailService().send_email(to_email=employee.email, subject=email_subject, body=email_body, is_html=False)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Chat task assignment email failed for {employee.email}: {e}")
        return f"Assigned \"{task.task_description}\" to {employee.name}.", [], [{
            "type": "Task", "label": task.task_description, "sublabel": f"Assigned to {employee.name}",
            "path": f"/daily-tasks/{task.id}",
        }]
    return "Something went wrong creating that task - please try again.", [], []


def _route_add_employee_action(m: str, db: Session, user_role: str):
    """"add new employee arpit" was being silently swallowed by the
    material parser (any "add ..." message matched it unconditionally),
    creating a fake material literally named "new employee arpit".
    This is the specific, named collision from the product brief -
    a targeted disambiguation check for this one real bug, not an
    expansion into broad keyword-rule territory. Checked before the
    material parser so it never gets a chance to misfire here."""
    match = re.match(r"^add\s+(?:a\s+|an\s+|new\s+)*employee\s+(?:named\s+)?(.+)", m)
    if not match:
        return None
    name = match.group(1).strip().rstrip(".")
    if not name:
        return None
    if user_role not in ("master",):
        return "Creating employees requires a master account.", [], None, None, []

    existing = db.query(Employee).filter(Employee.name.ilike(f"%{name}%")).first()
    if existing:
        return (
            f"There's already an employee named {existing.name}.", [], None, None,
            [{"type": "Employee", "label": existing.name, "sublabel": existing.designation or "",
              "path": f"/employees/{existing.id}"}],
        )

    display_name = " ".join(w.capitalize() for w in name.split())
    proposal = ProposedAction(
        action_type="create_employee",
        summary=f"Create employee \"{display_name}\"",
        payload={"name": display_name},
    )
    return f"Create a new employee named {display_name}?", [], proposal, None, []


def _route_leave_query(m: str, db: Session, current_employee_id: Optional[int], user_role: str = "user"):
    """"My leaves", "show Pankaj's leaves" - same real-data pattern as
    _route_task_query: "my" resolves through the actual
    User.employee_id link, a named person resolves through a live
    Employee.name query, never hard-coded. Works from any page,
    since it's checked unconditionally in _dispatch before any
    context-specific branch, not gated behind what record the user
    happened to be viewing when they opened the chat.

    Viewing a NAMED person's leaves is master-only, matching
    the exact same rule enforced on the real /api/leaves/ endpoint -
    the chatbot must not have looser permissions than the page it's
    standing in for."""
    if "leave" not in m:
        return None

    is_mine = any(w in m for w in ["my leave", "my leaves"])
    if is_mine:
        if current_employee_id is None:
            return ("Your account isn't linked to an employee record, so I can't look up "
                    "your leave records. Ask a master to link your account to your "
                    "employee profile."), [], []
        employee = db.query(Employee).filter(Employee.id == current_employee_id).first()
        return _leaves_for_employee(db, employee)

    name = _extract_employee_name_for_leaves(m)
    if name:
        if user_role not in ("master",):
            return "You can only view your own leave records.", [], []
        employee, ambiguous_matches = _resolve_employee_by_name(db, name)
        if ambiguous_matches:
            return _employee_ambiguity_message(name, ambiguous_matches), [], []
        if not employee:
            return f"I couldn't find an employee matching \"{name}\".", [], []
        return _leaves_for_employee(db, employee)

    return None


def _extract_employee_name_for_leaves(m: str) -> Optional[str]:
    patterns = [
        r"([a-z]+)'s\s+leaves?",
        r"leaves?\s+.*?\b(?:for|of)\s+([a-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, m)
        if match:
            return match.group(1)
    return None


def _leaves_for_employee(db: Session, employee):
    if not employee:
        return "I couldn't find that employee.", [], []
    leaves = db.query(Leave).filter(Leave.employee_id == employee.id).order_by(Leave.start_date.desc()).all()
    if not leaves:
        return f"{employee.name} has no leave records.", [], []
    records = [{
        "type": "Leave", "label": f"{leave.leave_type} - {leave.start_date.strftime('%d %b')} to {leave.end_date.strftime('%d %b %Y')}",
        "sublabel": f"{float(leave.days)} day(s) - {leave.status}",
        "path": "/leaves",
    } for leave in leaves[:10]]
    return f"{employee.name} has {len(leaves)} leave record(s).", [], records


def _route_salary_query(m: str):
    """The chatbot never handles salary at all - no data, no
    permission branching, no employee lookup. Any mention of salary
    gets the same redirect to the Salary section for every role."""
    if "salary" not in m:
        return None
    return (
        "Salary details aren't available through chat - please visit the Salary section to view or download salary slips.",
        [], [{"type": "SalarySlip", "label": "Salary", "sublabel": "View salary slips", "path": "/salary-slips"}],
    )


def _route_task_query(m: str, db: Session, current_employee_id: Optional[int]):
    """Handles every task-related question the assistant supports:
    "show my tasks", "show Pankaj's tasks", "what is Pankaj working
    on", "which of Pankaj's tasks are overdue", "which tasks are
    blocked". Employee names are resolved with a live query against
    Employee.name - never hard-coded, never a separate dataset -
    exactly the same table every other page reads from. Returns
    None (not a task query) so _dispatch falls through to its other
    branches."""
    is_task_query = any(w in m for w in ["task", "working on", "assigned"])
    if not is_task_query:
        return None

    wants_overdue = "overdue" in m
    wants_blocked = "blocked" in m

    is_mine = any(w in m for w in ["my task", "my tasks", "assigned to me", "i need to complete", "i need to do"])
    if is_mine:
        if current_employee_id is None:
            return ("Your account isn't linked to an employee record, so I can't look up "
                    "your tasks. Ask a master to link your account to your employee "
                    "profile."), [], []
        employee = db.query(Employee).filter(Employee.id == current_employee_id).first()
        return _tasks_for_employee(db, employee, overdue_only=wants_overdue)

    name = _extract_employee_name(m)
    if name:
        employee, ambiguous_matches = _resolve_employee_by_name(db, name)
        if ambiguous_matches:
            return _employee_ambiguity_message(name, ambiguous_matches), [], []
        if not employee:
            return f"I couldn't find an employee matching \"{name}\".", [], []
        return _tasks_for_employee(db, employee, overdue_only=wants_overdue)

    if wants_blocked:
        tasks = db.query(DailyTask).filter(DailyTask.status == "Blocked").all()
        return _format_task_results(tasks, f"{len(tasks)} tasks are currently blocked.")

    return None


def _extract_employee_name(m: str) -> Optional[str]:
    """Regex only, no hard-coded names - just recognizes the shape of
    a possessive or prepositional reference to a person and pulls out
    whatever word is in that position."""
    patterns = [
        r"([a-z]+)'s\s+tasks?",
        r"tasks?\s+(?:are\s+|is\s+)?(?:for|assigned to)\s+([a-z]+)",
        r"what\s+is\s+([a-z]+)\s+working",
        r"overdue\s+for\s+([a-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, m)
        if match:
            return match.group(1)
    return None


def _tasks_for_employee(db: Session, employee, overdue_only: bool = False):
    if not employee:
        return "I couldn't find that employee.", [], []
    query = db.query(DailyTask).filter(DailyTask.employee_id == employee.id)
    tasks = query.all()
    if overdue_only:
        today = datetime.utcnow().date()
        # Same definition of overdue used everywhere else this
        # applies (due date passed, not yet completed) - one
        # authoritative rule, not a chat-specific reinterpretation.
        tasks = [t for t in tasks if t.date.date() < today and t.status != "DONE"]
    label = f"{employee.name}'s {'overdue ' if overdue_only else ''}tasks"
    return _format_task_results(tasks, f"{len(tasks)} {label} found.")


def _format_task_results(tasks, summary_text: str):
    records = [{
        "type": "Task", "label": t.task_description,
        "sublabel": f"{t.status} - {t.completion_percent}% complete"
                    + (f" - Priority: {t.priority}" if t.priority else ""),
        "path": f"/daily-tasks/{t.id}",
    } for t in tasks[:10]]
    return summary_text, [], records


def _staff_summary(db: Session):
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    return f"{len(employees)} active employees on the team.", ["Show pending orders"], []


# --- payroll_service.py ---
"""Family P0.43 - Payroll Intelligence. A summary aggregation over
already-authoritative data (SalarySlip.status, SalaryAdvance) - not a
second payroll engine. Answers "is payroll ready, what's pending, what
remains" for one month/year, plus the business-wide (not month-
specific) outstanding salary-advance picture, since an advance can
span more than one recovery month.
"""

def get_payroll_summary(db: Session, month: str, year: str) -> dict:
    """One month's payroll state. employees_without_slip is a genuine
    "payroll not yet generated for them" finding (spec section 14 -
    "Payroll pending"), distinct from a slip that exists in "draft"
    status - the two are different findings and must not be
    conflated."""
    active_employees = db.query(Employee).filter(Employee.status == "Active").all()
    slips = db.query(SalarySlip).filter(SalarySlip.month == month, SalarySlip.year == year).all()
    slips_by_employee = {s.employee_id: s for s in slips}

    status_counts = {"draft": 0, "finalized": 0, "paid": 0}
    total_net_pending = Decimal("0")  # finalized but not yet paid
    total_net_paid = Decimal("0")
    total_advance_recovery = Decimal("0")
    for slip in slips:
        status_counts[slip.status] = status_counts.get(slip.status, 0) + 1
        total_advance_recovery += (slip.advance_deduction or Decimal("0"))
        if slip.status == "finalized":
            total_net_pending += (slip.net_salary or Decimal("0"))
        elif slip.status == "paid":
            total_net_paid += (slip.net_salary or Decimal("0"))

    employees_without_slip = [e for e in active_employees if e.id not in slips_by_employee]

    return {
        "month": month, "year": year,
        "total_active_employees": len(active_employees),
        "employees_with_slip": len(slips),
        "employees_without_slip": len(employees_without_slip),
        "employees_without_slip_names": [e.name for e in employees_without_slip],
        "status_counts": status_counts,
        "total_net_pending_payment": total_net_pending,
        "total_net_paid": total_net_paid,
        "total_advance_recovery_this_month": total_advance_recovery,
    }


def get_salary_advance_summary(db: Session) -> dict:
    """Business-wide (not month-specific), since one advance's
    recovery can genuinely span multiple payroll months (spec section
    10: "do not assume every advance must be recovered in one
    month")."""
    pending = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Pending").all()
    approved = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Approved").all()
    outstanding_total = sum((a.outstanding_amount for a in approved), Decimal("0"))
    fully_recovered = [a for a in approved if a.outstanding_amount <= 0]

    return {
        "pending_requests": len(pending),
        "approved_advances": len(approved),
        "fully_recovered_advances": len(fully_recovered),
        "advances_with_outstanding_balance": len(approved) - len(fully_recovered),
        "total_outstanding_amount": outstanding_total,
    }


def get_overtime_summary(db: Session, month: str, year: str) -> dict:
    """Real Attendance.overtime_hours records for the given month
    (parsed the same way salary_slips.py's own attendance-summary
    endpoint does) - which employees have approved overtime, and how
    much, never a second overtime calculation (Attendance.overtime_hours
    is the one authoritative, directly Master-set figure - see its own
    column comment)."""
    from datetime import datetime
    import calendar as _calendar
    from app.modules.hr.models import Attendance

    try:
        period_start = datetime.strptime(f"{month} {year}", "%B %Y")
    except ValueError:
        return {"month": month, "year": year, "error": "month must be a full month name, e.g. 'September', and year must be 4 digits", "employees": []}
    last_day = _calendar.monthrange(period_start.year, period_start.month)[1]
    period_end = period_start.replace(day=last_day, hour=23, minute=59, second=59)

    records = (
        db.query(Attendance)
        .filter(Attendance.date >= period_start, Attendance.date <= period_end, Attendance.overtime_hours > 0)
        .all()
    )
    by_employee: dict = {}
    for r in records:
        by_employee.setdefault(r.employee_id, Decimal("0"))
        by_employee[r.employee_id] += r.overtime_hours or Decimal("0")

    employee_ids = list(by_employee.keys())
    employees_by_id = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()} if employee_ids else {}

    return {
        "month": month, "year": year,
        "employees": [
            {"employee_id": eid, "employee_name": employees_by_id[eid].name if eid in employees_by_id else "Unknown", "total_overtime_hours": float(hours)}
            for eid, hours in by_employee.items()
        ],
    }


# --- working_calendar_service.py ---
"""Computes actual working days for a given month from the configured
working calendar - the explicit requirement that no
calculation assume a fixed 26 working days. Each month is calculated
independently from the current calendar configuration; nothing here
retroactively rewrites past records if the configuration later
changes (that's the caller's responsibility, matching "do not rewrite
historical finalized payroll records")."""

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


# --- Employee 360 / HR Command Center (Family 137, section 13) ---
"""Employee 360 aggregation/intelligence functions (spec subsections
13.1-13.14). Every function below is a read-only presentation layer
over existing Employee/Attendance/Leave/SalarySlip/SalaryAdvance/
DailyTask/ProductionJob/GenericDocument/AuditLog records - none of it
introduces a second HR data store or a second task/leave/attendance
system, matching the spec's own "do not create a separate parallel HR
system" rule. Every returned dict is tagged "label": "FACT" - nothing
here is a prediction, recommendation, or decision; where a figure
requires an explicit deterministic basis (e.g. the workload
classification) that basis is returned alongside it, never hidden."""


def _employee_task_query(db: Session, employee_id: int):
    return db.query(DailyTask).filter(DailyTask.employee_id == employee_id)


def employee_attendance_intelligence(db: Session, employee_id: int, months: int = 6) -> dict:
    """Section 13.2 - attendance percentage, present/absent/half-day
    counts, leave-marked days, overtime, and average working hours,
    extended from the existing Attendance capability. "Late"/"early
    departure"/"work from home" are not reported - Attendance has no
    shift-start-time or WFH field to derive them from honestly, and
    this project's own rule is to never invent a metric with no
    authoritative source."""
    from app.modules.hr.models import Attendance

    window_start = date.today().replace(day=1)
    for _ in range(months - 1):
        window_start = (window_start - timedelta(days=1)).replace(day=1)

    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= datetime.combine(window_start, datetime.min.time()),
    ).order_by(Attendance.date).all()

    present = sum(1 for r in records if r.attendance_status == "Present")
    half_day = sum(1 for r in records if r.attendance_status == "Half Day")
    absent = sum(1 for r in records if r.attendance_status == "Absent")
    on_leave = sum(1 for r in records if r.attendance_status == "Leave")
    total_marked = len(records)
    overtime_total = sum(float(r.overtime_hours or 0) for r in records)
    hours_records = [r.working_hours for r in records if r.in_time and r.out_time]
    avg_hours = round(sum(hours_records) / len(hours_records), 2) if hours_records else None
    attendance_percent = round(((present + half_day * 0.5) / total_marked) * 100, 1) if total_marked else None

    by_month = {}
    for r in records:
        key = r.date.strftime("%Y-%m")
        bucket = by_month.setdefault(key, {"present": 0, "absent": 0, "half_day": 0, "leave": 0, "overtime_hours": 0.0})
        status_key = {"Present": "present", "Absent": "absent", "Half Day": "half_day", "Leave": "leave"}.get(r.attendance_status)
        if status_key:
            bucket[status_key] += 1
        bucket["overtime_hours"] += float(r.overtime_hours or 0)

    return {
        "label": "FACT",
        "window_months": months,
        "total_records": total_marked,
        "present_days": present,
        "half_days": half_day,
        "absent_days": absent,
        "leave_marked_days": on_leave,
        "attendance_percent": attendance_percent,
        "overtime_hours_total": round(overtime_total, 2),
        "average_working_hours": avg_hours,
        "monthly_trend": [{"month": k, **v} for k, v in sorted(by_month.items())],
    }


def employee_calendar(db: Session, employee_id: int, year: int, month: int) -> Optional[dict]:
    """Section 13.3 - one monthly calendar per employee, built from the
    SAME working-day/holiday logic payroll already uses
    (get_working_dates) plus this employee's own Attendance and
    approved Leave rows. Never a second calendar/attendance-status
    system - every day is classified using only existing data."""
    from app.modules.hr.models import Attendance

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    working_dates = get_working_dates(db, year, month)
    holidays = {
        h.date: h for h in db.query(CompanyHoliday).filter(
            CompanyHoliday.date >= month_start, CompanyHoliday.date <= month_end,
        ).all()
    }
    attendance_by_date = {
        a.date.date(): a for a in db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= datetime.combine(month_start, datetime.min.time()),
            Attendance.date <= datetime.combine(month_end, datetime.max.time()),
        ).all()
    }
    approved_leaves = db.query(Leave).filter(
        Leave.employee_id == employee_id, Leave.status == "Approved",
        Leave.start_date <= datetime.combine(month_end, datetime.max.time()),
        Leave.end_date >= datetime.combine(month_start, datetime.min.time()),
    ).all()
    leave_dates = set()
    for lv in approved_leaves:
        current = max(lv.start_date.date(), month_start)
        end = min(lv.end_date.date(), month_end)
        while current <= end:
            leave_dates.add(current)
            current += timedelta(days=1)

    days = []
    for d in range(1, days_in_month + 1):
        current = date(year, month, d)
        attendance = attendance_by_date.get(current)
        event_type = _classify_attendance_day(current, attendance, leave_dates, holidays, working_dates)
        days.append({
            "date": current.isoformat(), "event_type": event_type,
            "holiday_name": holidays[current].name if current in holidays and not holidays[current].is_working else None,
        })

    return {
        "label": "FACT", "employee_id": employee_id, "employee_name": employee.name,
        "year": year, "month": month, "days": days,
    }


def _classify_attendance_day(current: date, attendance, leave_dates: set, holidays: dict, working_dates: set) -> str:
    """The single day-classification rule employee_calendar and the
    Attendance & Overtime Command Center's attendance_period_summary
    both use, extracted so a day is never classified two different
    ways in two different places. An existing Attendance record always
    wins (a recorded fact beats an inference); otherwise: approved
    leave, then a declared holiday, then "not a configured working
    day" (week off), and only then "an ordinary working day"."""
    status_map = {"Present": "present", "Half Day": "half_day", "Absent": "absent", "Leave": "leave"}
    if attendance:
        return status_map.get(attendance.attendance_status, "present")
    if current in leave_dates:
        return "leave"
    if current in holidays and not holidays[current].is_working:
        return "holiday"
    if current not in working_dates:
        return "week_off"
    return "work_day"


def _working_dates_in_range(db: Session, start_date: date, end_date: date) -> set:
    """get_working_dates is month-scoped; this unions it across every
    month a [start_date, end_date] range touches (a week or day view
    can still span a month boundary) and trims to the exact range."""
    dates = set()
    cursor = date(start_date.year, start_date.month, 1)
    while cursor <= end_date:
        dates |= get_working_dates(db, cursor.year, cursor.month)
        cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
    return {d for d in dates if start_date <= d <= end_date}


# --- Attendance & Overtime Command Center ---
"""Calendar-first Attendance & Overtime redesign. Every function below
computes Scheduled/Worked/Payable/Overtime/Shortfall from EXISTING
Attendance/Leave/CompanyHoliday/WorkingCalendarSettings/DailyTask/
ProductionOperation data using the SAME conventions already
established elsewhere in this codebase (see attendance_period_summary's
own docstring for the exact formulas) - no new business rules, no
per-employee schedule model, no frontend-side approximation of a
backend rule. Nothing here duplicates employee_calendar/
employee_attendance_intelligence above; attendance_period_summary
reuses _classify_attendance_day and is the richer, date-range-generic
sibling those two are now both consistent with."""

ATTENDANCE_DAY_VALUE = {"Present": 1, "Half Day": 0.5, "Absent": 0, "Leave": 0}


def attendance_period_summary(db: Session, employee_id: int, start_date: date, end_date: date) -> Optional[dict]:
    """The single per-employee, date-range aggregation call behind the
    KPI strip, the month/week calendar, and the day list.

    Scheduled hours = a day's Attendance.standard_hours if a record
    exists for it, else the model's own default (8) for a day that is
    an otherwise-ordinary configured working day with no record yet,
    else 0 for a day with no work expectation (holiday/week off/
    leave) - the same per-record standard_hours field payroll's own
    suggest_from_attendance already reads, applied per-day instead of
    "one record's value stands in for the whole month".

    Payable hours = (attendance-status day-value: Present=1,
    Half Day=0.5, Absent/Leave=0) x scheduled_hours + overtime_hours -
    literally the same day-value table get_payroll_summary/
    suggest_from_attendance already use for salary-in-rupees, applied
    here to hours instead.

    Shortfall hours = max(0, scheduled_hours - worked_hours) on a day
    the employee was expected to be at work (present/half_day/absent);
    zero on holiday/week_off/leave, where there was no expectation to
    fall short of.

    Attendance % uses the exact same formula as
    employee_attendance_intelligence - (present + half_day*0.5) /
    total_marked_records - scoped to this range's actual records, so
    "attendance %" is never defined two different ways in this app."""
    from app.modules.hr.models import Attendance

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    records_by_date = {
        r.date.date(): r for r in db.query(Attendance).filter(
            Attendance.employee_id == employee_id, Attendance.date >= start_dt, Attendance.date <= end_dt,
        ).all()
    }
    approved_leaves = db.query(Leave).filter(
        Leave.employee_id == employee_id, Leave.status == "Approved",
        Leave.start_date <= end_dt, Leave.end_date >= start_dt,
    ).all()
    leave_dates = set()
    for lv in approved_leaves:
        current = max(lv.start_date.date(), start_date)
        stop = min(lv.end_date.date(), end_date)
        while current <= stop:
            leave_dates.add(current)
            current += timedelta(days=1)
    holidays = {
        h.date: h for h in db.query(CompanyHoliday).filter(
            CompanyHoliday.date >= start_date, CompanyHoliday.date <= end_date,
        ).all()
    }
    working_dates = _working_dates_in_range(db, start_date, end_date)
    task_counts = {}
    for t in db.query(DailyTask).filter(
        DailyTask.employee_id == employee_id, DailyTask.date >= start_dt, DailyTask.date <= end_dt,
    ).all():
        task_counts[t.date.date()] = task_counts.get(t.date.date(), 0) + 1

    days = []
    totals = {"scheduled_hours": 0.0, "worked_hours": 0.0, "payable_hours": 0.0, "overtime_hours": 0.0, "shortfall_hours": 0.0}
    marked_records = 0
    present_equivalent = 0.0

    current = start_date
    while current <= end_date:
        record = records_by_date.get(current)
        event_type = _classify_attendance_day(current, record, leave_dates, holidays, working_dates)
        is_expected_work_day = event_type in ("present", "half_day", "absent")

        if record:
            scheduled_hours = float(record.standard_hours or 0)
            worked_hours = record.working_hours
            overtime_hours = float(record.overtime_hours or 0)
        elif event_type == "work_day":
            scheduled_hours, worked_hours, overtime_hours = 8.0, 0.0, 0.0
        else:
            scheduled_hours = worked_hours = overtime_hours = 0.0

        day_value = ATTENDANCE_DAY_VALUE.get(record.attendance_status, 0) if record else 0
        payable_hours = round(day_value * scheduled_hours + overtime_hours, 2)
        shortfall_hours = round(max(0.0, scheduled_hours - worked_hours), 2) if is_expected_work_day else 0.0

        days.append({
            "date": current.isoformat(), "event_type": event_type,
            "attendance_status": record.attendance_status if record else None,
            "in_time": record.in_time.isoformat() if record and record.in_time else None,
            "out_time": record.out_time.isoformat() if record and record.out_time else None,
            "scheduled_hours": scheduled_hours, "worked_hours": worked_hours,
            "payable_hours": payable_hours, "overtime_hours": overtime_hours, "shortfall_hours": shortfall_hours,
            "holiday_name": holidays[current].name if current in holidays and not holidays[current].is_working else None,
            "task_count": task_counts.get(current, 0),
            "has_missing_checkout": bool(record and record.in_time and not record.out_time),
        })

        totals["scheduled_hours"] += scheduled_hours
        totals["worked_hours"] += worked_hours
        totals["payable_hours"] += payable_hours
        totals["overtime_hours"] += overtime_hours
        totals["shortfall_hours"] += shortfall_hours
        if record:
            marked_records += 1
            present_equivalent += ATTENDANCE_DAY_VALUE.get(record.attendance_status, 0)

        current += timedelta(days=1)

    attendance_percent = round(present_equivalent / marked_records * 100, 1) if marked_records else None

    return {
        "label": "FACT",
        "employee_id": employee.id, "employee_name": employee.name,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "summary": {
            **{k: round(v, 2) for k, v in totals.items()},
            "attendance_percent": attendance_percent,
        },
        "days": days,
    }


def attendance_day_detail(db: Session, employee_id: int, target_date: date) -> Optional[dict]:
    """The day-detail panel's single call: that day's attendance
    figures (reusing attendance_period_summary called with a one-day
    range, so the two never disagree) plus the work/task allocation
    and timeline for that day, built entirely from existing DailyTask/
    ProductionOperation data - never a second time-allocation system.

    Only entries that genuinely carry a start/end time are placed on
    the timeline (spec: "do not invent a frontend approximation" -
    a task with no planned_start/planned_end is real work but has no
    real time span, so it is listed separately rather than given a
    fabricated slot)."""
    from app.modules.operations.models import ProductionOperation
    from app.modules.sales.models import Order

    period = attendance_period_summary(db, employee_id, target_date, target_date)
    if period is None:
        return None
    day = period["days"][0]

    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    tasks = db.query(DailyTask).filter(
        DailyTask.employee_id == employee_id, DailyTask.date >= start_dt, DailyTask.date <= end_dt,
    ).order_by(DailyTask.planned_start).all()
    operations = db.query(ProductionOperation).filter(
        ProductionOperation.employee_id == employee_id,
        ProductionOperation.start_time >= start_dt, ProductionOperation.start_time <= end_dt,
    ).order_by(ProductionOperation.start_time).all()

    order_ids = {t.order_id for t in tasks if t.order_id} | {
        op.production_job.order_id for op in operations if op.production_job and op.production_job.order_id
    }
    order_codes = {
        o.id: o.order_code for o in db.query(Order).filter(Order.id.in_(order_ids)).all()
    } if order_ids else {}

    timeline = []
    unscheduled = []
    for t in tasks:
        entry = {
            "type": "task", "id": t.id, "task_code": t.task_code, "description": t.task_description,
            "order_id": t.order_id, "order_code": order_codes.get(t.order_id), "status": t.status,
        }
        if t.planned_start and t.planned_end:
            # DailyTask.planned_start/planned_end are bare `time`
            # values (no date component) - combined with target_date
            # here so this entry's start/end are full ISO datetimes,
            # the SAME shape ProductionOperation entries use below.
            # Without this, sorting/rendering the timeline would mix
            # "14:30:00" strings with "2026-09-11T14:30:00" ones and
            # order incorrectly.
            timeline.append({
                **entry,
                "start": datetime.combine(target_date, t.planned_start).isoformat(),
                "end": datetime.combine(target_date, t.planned_end).isoformat(),
            })
        else:
            unscheduled.append(entry)
    for op in operations:
        entry = {
            "type": "production_operation", "id": op.id, "operation_name": op.operation_name,
            "order_id": op.production_job.order_id if op.production_job else None,
            "order_code": order_codes.get(op.production_job.order_id if op.production_job else None),
            "status": op.status,
        }
        if op.start_time and op.end_time:
            timeline.append({**entry, "start": op.start_time.isoformat(), "end": op.end_time.isoformat()})
        else:
            unscheduled.append(entry)
    timeline.sort(key=lambda e: e["start"])

    return {
        "label": "FACT",
        "employee_id": employee_id, "employee_name": period["employee_name"], "date": target_date.isoformat(),
        **day,
        "timeline": timeline,
        "unscheduled_work": unscheduled,
    }


def apply_overtime_hours(db: Session, employee_id: int, target_date, hours, mode: str = "set"):
    """The single function that writes Attendance.overtime_hours -
    used by both the existing bulk 'Manage Overtime' action
    (POST /api/attendance/overtime, direct Master corrections) and the
    new OvertimeRequest approval flow, so this authoritative figure is
    never computed or written by two different code paths. Does not
    commit - the caller controls the transaction (the bulk action
    applies this in a loop across dates before one final commit; the
    approval route applies it once alongside the OvertimeRequest's own
    status change).

    Creates a bare Attendance record (attendance_status="Present",
    overtime_hours=0 before applying) if none exists for the date -
    a bare overtime entry makes no claim about regular attendance that
    day, so it is deliberately not "Absent"/"Leave" either (same rule
    as the pre-existing bulk action)."""
    from app.modules.hr.models import Attendance

    if hasattr(target_date, "date") and not isinstance(target_date, date):
        target_date = target_date.date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    record = db.query(Attendance).filter(
        Attendance.employee_id == employee_id, Attendance.date >= day_start, Attendance.date < day_end,
    ).with_for_update().first()

    if not record:
        record = Attendance(
            business_id=generate_business_id(db), date=day_start, employee_id=employee_id,
            attendance_status="Present", overtime_hours=0,
        )
        db.add(record)
        db.flush()

    if mode == "add":
        record.overtime_hours = (record.overtime_hours or 0) + hours
    else:
        record.overtime_hours = hours
    db.add(record)
    return record


def team_attendance_grid(db: Session, start_date: date, end_date: date, department: Optional[str] = None) -> dict:
    """The Master team-grid view (Employee x day, spec section 7) as
    ONE call for the whole range and every employee - not one
    attendance_period_summary call per employee, which is exactly the
    N+1 the spec's performance section (12) forbids. Shares the same
    per-day classification (_classify_attendance_day) and Payable
    formula (ATTENDANCE_DAY_VALUE) as attendance_period_summary, so a
    day is never worth a different thing in the grid than it is in an
    individual employee's own view.

    Caller is responsible for the master-only check (same convention
    as every other master-scoped route in this module) - this function
    itself does not know about roles."""
    from app.modules.hr.models import Attendance

    query = db.query(Employee).filter(Employee.status == "Active")
    if department:
        query = query.filter(Employee.department == department)
    employees = query.order_by(Employee.name).all()
    employee_ids = [e.id for e in employees]
    if not employee_ids:
        return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "employees": []}

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    records_by_employee = {}
    for r in db.query(Attendance).filter(
        Attendance.employee_id.in_(employee_ids), Attendance.date >= start_dt, Attendance.date <= end_dt,
    ).all():
        records_by_employee.setdefault(r.employee_id, {})[r.date.date()] = r

    leave_dates_by_employee = {}
    for lv in db.query(Leave).filter(
        Leave.employee_id.in_(employee_ids), Leave.status == "Approved",
        Leave.start_date <= end_dt, Leave.end_date >= start_dt,
    ).all():
        current = max(lv.start_date.date(), start_date)
        stop = min(lv.end_date.date(), end_date)
        bucket = leave_dates_by_employee.setdefault(lv.employee_id, set())
        while current <= stop:
            bucket.add(current)
            current += timedelta(days=1)

    holidays = {
        h.date: h for h in db.query(CompanyHoliday).filter(
            CompanyHoliday.date >= start_date, CompanyHoliday.date <= end_date,
        ).all()
    }
    working_dates = _working_dates_in_range(db, start_date, end_date)

    result_employees = []
    for employee in employees:
        emp_records = records_by_employee.get(employee.id, {})
        emp_leave_dates = leave_dates_by_employee.get(employee.id, set())
        days = []
        totals = {"scheduled_hours": 0.0, "worked_hours": 0.0, "payable_hours": 0.0, "overtime_hours": 0.0, "shortfall_hours": 0.0}
        marked_records = 0
        present_equivalent = 0.0

        current = start_date
        while current <= end_date:
            record = emp_records.get(current)
            event_type = _classify_attendance_day(current, record, emp_leave_dates, holidays, working_dates)
            is_expected_work_day = event_type in ("present", "half_day", "absent")

            if record:
                scheduled_hours = float(record.standard_hours or 0)
                worked_hours = record.working_hours
                overtime_hours = float(record.overtime_hours or 0)
            elif event_type == "work_day":
                scheduled_hours, worked_hours, overtime_hours = 8.0, 0.0, 0.0
            else:
                scheduled_hours = worked_hours = overtime_hours = 0.0

            day_value = ATTENDANCE_DAY_VALUE.get(record.attendance_status, 0) if record else 0
            payable_hours = round(day_value * scheduled_hours + overtime_hours, 2)
            shortfall_hours = round(max(0.0, scheduled_hours - worked_hours), 2) if is_expected_work_day else 0.0

            days.append({
                "date": current.isoformat(), "event_type": event_type,
                "overtime_hours": overtime_hours, "shortfall_hours": shortfall_hours,
                "has_missing_checkout": bool(record and record.in_time and not record.out_time),
            })
            totals["scheduled_hours"] += scheduled_hours
            totals["worked_hours"] += worked_hours
            totals["payable_hours"] += payable_hours
            totals["overtime_hours"] += overtime_hours
            totals["shortfall_hours"] += shortfall_hours
            if record:
                marked_records += 1
                present_equivalent += ATTENDANCE_DAY_VALUE.get(record.attendance_status, 0)
            current += timedelta(days=1)

        attendance_percent = round(present_equivalent / marked_records * 100, 1) if marked_records else None
        result_employees.append({
            "employee_id": employee.id, "employee_name": employee.name, "department": employee.department,
            "designation": employee.designation,
            "days": days,
            "summary": {**{k: round(v, 2) for k, v in totals.items()}, "attendance_percent": attendance_percent},
        })

    return {"label": "FACT", "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "employees": result_employees}


def attendance_exceptions(db: Session, employee_id: Optional[int], start_date: date, end_date: date) -> dict:
    """The 'what needs my attention' feed (spec section 8). Every
    exception here is a real, backend-observable fact - never an
    invented threshold. Deliberately does NOT include an "excessive
    overtime" category: Woodful has no configured per-employee/company
    overtime ceiling today, and inventing one client-side (or with a
    silently made-up number here) is exactly what spec section 6/13
    forbid ("if a calculation is not currently supported by the
    backend, do not invent a frontend approximation - identify what
    backend enhancement is required"). A future WorkingCalendarSettings
    field for this would be the correct backend enhancement.

    employee_id=None scopes to every active employee - caller is
    responsible for the master-only check, same convention as
    team_attendance_grid."""
    from app.modules.hr.models import Attendance, OvertimeRequest

    query = db.query(Employee).filter(Employee.status == "Active")
    if employee_id:
        query = query.filter(Employee.id == employee_id)
    employees = {e.id: e for e in query.all()}
    employee_ids = list(employees.keys())
    if not employee_ids:
        return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "exceptions": []}

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    today = date.today()

    records_by_employee = {}
    for r in db.query(Attendance).filter(
        Attendance.employee_id.in_(employee_ids), Attendance.date >= start_dt, Attendance.date <= end_dt,
    ).all():
        records_by_employee.setdefault(r.employee_id, {})[r.date.date()] = r

    leave_dates_by_employee = {}
    for lv in db.query(Leave).filter(
        Leave.employee_id.in_(employee_ids), Leave.status == "Approved",
        Leave.start_date <= end_dt, Leave.end_date >= start_dt,
    ).all():
        current = max(lv.start_date.date(), start_date)
        stop = min(lv.end_date.date(), end_date)
        bucket = leave_dates_by_employee.setdefault(lv.employee_id, set())
        while current <= stop:
            bucket.add(current)
            current += timedelta(days=1)

    holidays = {
        h.date: h for h in db.query(CompanyHoliday).filter(
            CompanyHoliday.date >= start_date, CompanyHoliday.date <= end_date,
        ).all()
    }
    working_dates = _working_dates_in_range(db, start_date, end_date)

    submitted_requests = db.query(OvertimeRequest).filter(
        OvertimeRequest.employee_id.in_(employee_ids), OvertimeRequest.status == "Submitted",
        OvertimeRequest.date >= start_dt, OvertimeRequest.date <= end_dt,
    ).all()
    approved_request_keys = {
        (r.employee_id, r.date.date())
        for r in db.query(OvertimeRequest).filter(
            OvertimeRequest.employee_id.in_(employee_ids), OvertimeRequest.status == "Approved",
            OvertimeRequest.date >= start_dt, OvertimeRequest.date <= end_dt,
        ).all()
    }

    exceptions = []
    for eid in employee_ids:
        employee = employees[eid]
        emp_records = records_by_employee.get(eid, {})
        emp_leave_dates = leave_dates_by_employee.get(eid, set())
        current = start_date
        while current <= end_date:
            record = emp_records.get(current)
            event_type = _classify_attendance_day(current, record, emp_leave_dates, holidays, working_dates)

            if event_type == "work_day" and current < today:
                exceptions.append(_exception(employee, current, "missing_attendance",
                                              "No attendance record for a scheduled working day.", "high"))
            elif event_type == "holiday" and record and record.attendance_status in ("Present", "Half Day"):
                exceptions.append(_exception(employee, current, "holiday_conflict",
                                              f"Marked {record.attendance_status} on a declared holiday ({holidays[current].name}).", "medium"))
            elif event_type == "leave" and record and record.attendance_status in ("Present", "Half Day"):
                exceptions.append(_exception(employee, current, "leave_conflict",
                                              f"Marked {record.attendance_status} while on approved leave.", "medium"))

            if record:
                if record.in_time and not record.out_time and current < today:
                    exceptions.append(_exception(employee, current, "missing_checkout",
                                                  "Checked in but never checked out.", "high"))
                scheduled_hours = float(record.standard_hours or 0)
                if event_type in ("present", "half_day", "absent") and record.working_hours < scheduled_hours and current < today:
                    exceptions.append(_exception(employee, current, "shortfall",
                                                  f"Worked {record.working_hours:.1f}h of {scheduled_hours:.1f}h scheduled.", "low"))
                if float(record.overtime_hours or 0) > 0 and (eid, current) not in approved_request_keys:
                    exceptions.append(_exception(employee, current, "overtime_without_request",
                                                  f"{float(record.overtime_hours):.1f}h overtime recorded without an approved overtime request.", "medium"))
            current += timedelta(days=1)

    for req in submitted_requests:
        employee = employees.get(req.employee_id)
        if not employee:
            continue
        exceptions.append(_exception(employee, req.date.date(), "unapproved_overtime",
                                      f"{float(req.requested_hours):.1f}h overtime request pending approval.", "high",
                                      extra={"overtime_request_id": req.id}))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    exceptions.sort(key=lambda e: (severity_rank.get(e["severity"], 3), e["date"], e["employee_name"]))
    return {"label": "FACT", "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "exceptions": exceptions}


def _exception(employee, day: date, exception_type: str, message: str, severity: str, extra: Optional[dict] = None) -> dict:
    item = {
        "employee_id": employee.id, "employee_name": employee.name, "date": day.isoformat(),
        "type": exception_type, "message": message, "severity": severity,
    }
    if extra:
        item.update(extra)
    return item


def employee_leave_summary(db: Session, employee_id: int) -> Optional[dict]:
    """Section 13.4 - per-type/per-status leave counts using the
    existing Leave model/workflow. Does not report a leave
    "balance"/quota figure - Woodful has no configured leave-policy/
    quota source, and inventing one would violate this project's own
    "do not invent metrics" rule; usage history is shown instead."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    all_leaves = db.query(Leave).filter(Leave.employee_id == employee_id).order_by(Leave.start_date.desc()).all()
    year_start = datetime(date.today().year, 1, 1)
    approved_this_year = [l for l in all_leaves if l.start_date >= year_start and l.status == "Approved"]
    by_type = {}
    for l in approved_this_year:
        by_type[l.leave_type] = by_type.get(l.leave_type, 0) + float(l.days or 0)

    return {
        "label": "FACT",
        "pending_requests": sum(1 for l in all_leaves if l.status == "Pending"),
        "approved_this_year_by_type": by_type,
        "approved_days_this_year": round(sum(by_type.values()), 1),
        "rejected_count": sum(1 for l in all_leaves if l.status == "Rejected"),
        "recent": [{
            "id": l.id, "leave_type": l.leave_type, "start_date": l.start_date.isoformat(),
            "end_date": l.end_date.isoformat(), "days": float(l.days or 0), "status": l.status,
            "approved_by": l.approved_by, "reason": l.reason,
        } for l in all_leaves[:20]],
        "note": "No leave balance/quota is shown - Woodful has no configured leave-policy or quota source yet, so this is usage history rather than a remaining-balance figure.",
    }


def employee_work_intelligence(db: Session, employee_id: int) -> dict:
    """Section 13.5 - assigned/active/completed/blocked/overdue/
    upcoming task counts and completion rate, from the existing
    Productivity/Daily Tasks capability. Never a duplicate task
    system."""
    tasks = _employee_task_query(db, employee_id).all()
    today_dt = datetime.combine(date.today(), datetime.min.time())
    completed = [t for t in tasks if t.status == "DONE"]
    blocked = [t for t in tasks if t.status == "BLOCKED"]
    active = [t for t in tasks if t.status in ("TO DO", "DOING")]
    overdue = sorted([t for t in active if t.date < today_dt], key=lambda t: t.date)
    upcoming = [t for t in active if t.date >= today_dt]
    completion_rate = round(len(completed) / len(tasks) * 100, 1) if tasks else None

    return {
        "label": "FACT",
        "assigned_total": len(tasks),
        "active": len(active),
        "completed": len(completed),
        "blocked": len(blocked),
        "overdue": len(overdue),
        "upcoming": len(upcoming),
        "completion_rate_percent": completion_rate,
        "overdue_tasks": [{
            "id": t.id, "task_code": t.task_code, "description": t.task_description, "date": t.date.isoformat(),
        } for t in overdue[:10]],
    }


def employee_workload(db: Session, employee_id: int) -> dict:
    """Section 13.6 - a Low/Medium/High workload classification with
    an explicit, deterministic, documented basis (never a hidden or
    opaque score): weighted points = active tasks + (overdue tasks x
    2); Low under 3, Medium 3-7, High 8+."""
    work = employee_work_intelligence(db, employee_id)
    active_tasks = _employee_task_query(db, employee_id).filter(DailyTask.status.in_(("TO DO", "DOING"))).all()
    horizon = datetime.combine(date.today() + timedelta(days=7), datetime.min.time())
    due_soon = sum(1 for t in active_tasks if t.date <= horizon)

    score = work["active"] + work["overdue"] * 2
    if score >= 8:
        level = "High"
    elif score >= 3:
        level = "Medium"
    else:
        level = "Low"

    return {
        "label": "FACT",
        "workload_level": level,
        "basis": "Weighted points = active tasks + (overdue tasks x 2). Low: under 3 points. Medium: 3-7 points. High: 8+ points.",
        "weighted_points": score,
        "active_tasks": work["active"],
        "overdue_tasks": work["overdue"],
        "due_within_7_days": due_soon,
    }


def employee_relationships(db: Session, employee_id: int) -> Optional[dict]:
    """Section 13.11 - existing organizational relationships only
    (manager, direct reports, department peers, related orders) -
    never a new org-chart data store. manager is free text on Employee
    (see hr/models.py's own comment on why it is not a self-
    referential FK), so direct reports are matched by
    manager-name-equals-this-employee's-name, the same way the rest of
    this codebase already treats that field."""
    from app.modules.sales.models import Order

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    manager_employee = db.query(Employee).filter(Employee.name == employee.manager).first() if employee.manager else None
    direct_reports = db.query(Employee).filter(Employee.manager == employee.name, Employee.id != employee.id).all()
    peers = (
        db.query(Employee).filter(Employee.department == employee.department, Employee.id != employee.id).all()
        if employee.department else []
    )
    order_ids = {
        t.order_id for t in _employee_task_query(db, employee_id).filter(DailyTask.order_id.isnot(None)).all()
    }
    orders = db.query(Order).filter(Order.id.in_(order_ids)).all() if order_ids else []

    return {
        "label": "FACT",
        "manager": (
            {"id": manager_employee.id, "name": manager_employee.name} if manager_employee
            else ({"id": None, "name": employee.manager} if employee.manager else None)
        ),
        "direct_reports": [{"id": e.id, "name": e.name, "designation": e.designation} for e in direct_reports],
        "department": employee.department,
        "department_peers": [{"id": e.id, "name": e.name} for e in peers],
        "related_orders": [{"id": o.id, "order_code": o.order_code, "status": o.project_status} for o in orders][:20],
    }


def employee_cost_contribution(db: Session, employee_id: int, months: int = 6) -> Optional[dict]:
    """Section 13.14 - factual cost and work-contribution visibility,
    explicitly NOT an employee "profitability" score (the spec
    forbids inventing one). Cost = all finalized/paid SalarySlip net
    salary and overtime amounts on file; contribution = completed
    tasks and production jobs within the trailing `months`-month
    window, since those have real dates to window by (SalarySlip only
    has month/year strings, so its totals are reported as an honest
    all-time figure rather than an unreliable date-windowed one)."""
    from app.modules.operations.models import ProductionJob

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    window_start = date.today().replace(day=1)
    for _ in range(months - 1):
        window_start = (window_start - timedelta(days=1)).replace(day=1)
    window_start_dt = datetime.combine(window_start, datetime.min.time())

    slips = db.query(SalarySlip).filter(
        SalarySlip.employee_id == employee_id, SalarySlip.status.in_(("finalized", "paid")),
    ).all()
    total_net = sum(float(s.net_salary or 0) for s in slips)
    total_overtime_amount = sum(float(s.overtime_amount or 0) for s in slips)

    completed_tasks = _employee_task_query(db, employee_id).filter(
        DailyTask.status == "DONE", DailyTask.date >= window_start_dt,
    ).count()
    completed_jobs = db.query(ProductionJob).filter(
        ProductionJob.employee_id == employee_id, ProductionJob.status == "Completed",
        ProductionJob.date >= window_start_dt,
    ).count()

    return {
        "label": "FACT",
        "window_months": months,
        "salary_slips_considered": len(slips),
        "total_salary_cost_all_time_finalized_or_paid": round(total_net, 2),
        "total_overtime_amount_all_time_finalized_or_paid": round(total_overtime_amount, 2),
        "completed_tasks_in_window": completed_tasks,
        "completed_production_jobs_in_window": completed_jobs,
        "disclaimer": "Factual cost and work-contribution figures only - not, and must not be treated as, an employee profitability or performance score.",
    }


def employee_needs_attention(db: Session, employee_id: int, can_view_documents: bool = True) -> Optional[dict]:
    """Section 13.12 - a real, condition-based exception list, never
    generated merely for visual completeness. Each item links to the
    existing workflow it concerns.

    can_view_documents gates the expiring/expired-document items to
    master-only callers, matching the stricter rule the Documents API
    already enforces for the "employee" parent type (see
    documents/api.py's SENSITIVE_PARENT_TYPES) - an employee's own
    Employee 360 read must not surface document facts the plain
    Documents endpoint would refuse them."""
    from app.modules.documents.api import GenericDocument

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    items = []
    work = employee_work_intelligence(db, employee_id)
    if work["overdue"]:
        items.append({
            "type": "overdue_tasks", "severity": "high",
            "text": f"{work['overdue']} overdue task(s).", "path": f"/employees/{employee_id}",
        })

    pending_leaves = db.query(Leave).filter(Leave.employee_id == employee_id, Leave.status == "Pending").count()
    if pending_leaves:
        items.append({
            "type": "pending_leave_approval", "severity": "medium",
            "text": f"{pending_leaves} leave request(s) awaiting approval.", "path": "/leaves",
        })

    pending_advances = db.query(SalaryAdvance).filter(
        SalaryAdvance.employee_id == employee_id, SalaryAdvance.status == "Pending",
    ).count()
    if pending_advances:
        items.append({
            "type": "pending_salary_advance", "severity": "medium",
            "text": f"{pending_advances} salary advance request(s) awaiting approval.", "path": "/salary-advances",
        })

    if can_view_documents:
        today_date = date.today()
        soon = today_date + timedelta(days=30)
        docs = db.query(GenericDocument).filter(
            GenericDocument.parent_type == "employee", GenericDocument.parent_id == employee_id,
            GenericDocument.expiry_date.isnot(None), GenericDocument.expiry_date <= soon,
        ).all()
        for d in docs:
            is_expired = d.expiry_date < today_date
            items.append({
                "type": "expired_document" if is_expired else "expiring_document",
                "severity": "high" if is_expired else "medium",
                "text": f"Document \"{d.original_filename}\" {'expired' if is_expired else 'expires'} {d.expiry_date.isoformat()}.",
                "path": f"/employees/{employee_id}",
            })

    if employee.status == "Active":
        onboarding = employee_lifecycle(db, employee_id, "onboarding")
        incomplete = [i for i in onboarding["items"] if not i["is_complete"]] if onboarding else []
        if incomplete:
            items.append({
                "type": "pending_onboarding", "severity": "low",
                "text": f"{len(incomplete)} onboarding item(s) not yet complete.", "path": f"/employees/{employee_id}",
            })

    return {"label": "FACT", "total": len(items), "items": items}


def employee_lifecycle(db: Session, employee_id: int, phase: str) -> Optional[dict]:
    """Section 13.9 - onboarding/offboarding checklist. Seeds the
    fixed catalog for this employee/phase on first read (an employee
    created before this feature existed is backfilled the same way,
    the next time anyone opens their record). Offboarding items are
    only seeded once the employee's status is actually "Inactive" - a
    still-active employee has no offboarding to track.

    Auto-derivable onboarding items (see ONBOARDING_AUTO_ITEMS) are
    recomputed from live Employee/Documents data on every read rather
    than trusted from the stored row, so "progress" always reflects
    actual completion, not a stale checkbox."""
    from app.modules.documents.api import GenericDocument
    from app.modules.hr.models import (
        EmployeeLifecycleItem, ONBOARDING_ITEMS, OFFBOARDING_ITEMS, ONBOARDING_AUTO_ITEMS, LIFECYCLE_PHASES,
    )

    if phase not in LIFECYCLE_PHASES:
        return None
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    catalog = ONBOARDING_ITEMS if phase == "onboarding" else OFFBOARDING_ITEMS
    catalog_keys = [key for key, _ in catalog]
    existing = {
        i.item_key: i for i in db.query(EmployeeLifecycleItem).filter(
            EmployeeLifecycleItem.employee_id == employee_id, EmployeeLifecycleItem.phase == phase,
        ).all()
    }

    if phase == "offboarding" and employee.status != "Inactive" and not existing:
        return {"employee_id": employee_id, "phase": phase, "items": []}

    for key, label in catalog:
        if key not in existing:
            row = EmployeeLifecycleItem(employee_id=employee_id, phase=phase, item_key=key, label=label)
            db.add(row)
            existing[key] = row
    db.commit()

    if phase == "onboarding":
        has_documents = db.query(GenericDocument).filter(
            GenericDocument.parent_type == "employee", GenericDocument.parent_id == employee_id,
        ).count() > 0
        live_facts = {
            "record_created": True,
            "documents_submitted": has_documents,
            "role_assigned": bool(employee.designation),
            "manager_assigned": bool(employee.manager),
        }
        for key, value in live_facts.items():
            row = existing.get(key)
            if row is not None and row.is_complete != value:
                row.is_complete = value
                row.completed_date = datetime.utcnow() if value else None
                row.completed_by = "system"
                db.add(row)
        db.commit()

    items = [existing[key] for key in catalog_keys]
    return {
        "employee_id": employee_id, "phase": phase,
        "items": [{
            "id": i.id, "item_key": i.item_key, "label": i.label, "is_complete": i.is_complete,
            "completed_date": i.completed_date.isoformat() if i.completed_date else None,
            "completed_by": i.completed_by, "remarks": i.remarks,
            "auto_computed": phase == "onboarding" and i.item_key in ONBOARDING_AUTO_ITEMS,
        } for i in items],
    }


def _describe_employee_audit(entry) -> str:
    """Turns one employees-module AuditLog row into a human-readable
    activity-timeline line, diffing old_value/new_value for the fields
    the spec explicitly calls out (section 13.10: "salary changes,
    designation changes")."""
    if entry.action == "create_employee":
        return "Employee record created."
    if entry.action == "delete_employee":
        return "Employee record deleted."
    if entry.action == "update_employee":
        old = entry.old_value or {}
        new = entry.new_value or {}
        changed = [
            f"{field.replace('_', ' ')}: {old.get(field)} -> {new.get(field)}"
            for field in ("designation", "department", "status", "monthly_salary", "manager")
            if field in new and old.get(field) != new.get(field)
        ]
        return ("Employee updated (" + "; ".join(changed) + ").") if changed else "Employee record updated."
    return entry.action.replace("_", " ").capitalize() + "."


def employee_activity_timeline(db: Session, employee_id: int, limit: int = 200,
                                can_view_documents: bool = True) -> Optional[dict]:
    """Section 13.10 - a chronological activity view aggregated purely
    from existing authoritative records (Leave, SalarySlip,
    SalaryAdvance, GenericDocument, EmployeeLifecycleItem, and this
    employee's own AuditLog rows) - the same "no redundant timeline
    table" pattern already used for the Client Relationship Timeline
    (see clients/services.py's client_relationship_timeline).

    can_view_documents gates document-upload entries to master-only
    callers, same rationale as employee_needs_attention's own
    can_view_documents parameter."""
    from app.platform.audit import AuditLog
    from app.modules.documents.api import GenericDocument
    from app.modules.hr.models import EmployeeLifecycleItem

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    entries = []

    for l in db.query(Leave).filter(Leave.employee_id == employee_id).all():
        entries.append({
            "type": "leave", "subtype": l.status.lower(), "date": l.created_at, "author": l.approved_by,
            "text": f"{l.leave_type} leave request ({l.start_date.date()} to {l.end_date.date()}, {float(l.days or 0)} day(s)) - {l.status}.",
            "path": "/leaves",
        })

    for s in db.query(SalarySlip).filter(SalarySlip.employee_id == employee_id).all():
        entries.append({
            "type": "salary_slip", "subtype": s.status, "date": s.created_at, "author": None,
            "text": f"Salary slip for {s.month} {s.year} - {s.status}.", "path": "/salary-slips",
        })

    for a in db.query(SalaryAdvance).filter(SalaryAdvance.employee_id == employee_id).all():
        if a.status == "Approved":
            text = f"Salary advance approved: {float(a.approved_amount or 0):,.2f}."
        elif a.status == "Rejected":
            text = f"Salary advance rejected (requested {float(a.requested_amount):,.2f})."
        else:
            text = f"Salary advance requested: {float(a.requested_amount):,.2f}."
        entries.append({
            "type": "salary_advance", "subtype": a.status.lower(), "date": a.request_date, "author": a.approved_by,
            "text": text, "path": "/salary-advances",
        })

    if can_view_documents:
        for d in db.query(GenericDocument).filter(
            GenericDocument.parent_type == "employee", GenericDocument.parent_id == employee_id,
        ).all():
            entries.append({
                "type": "document", "subtype": "upload", "date": d.created_at, "author": d.uploaded_by,
                "text": f"Document uploaded: {d.original_filename}" + (f" ({d.document_type})" if d.document_type else ""),
                "path": f"/employees/{employee_id}",
            })

    for i in db.query(EmployeeLifecycleItem).filter(
        EmployeeLifecycleItem.employee_id == employee_id, EmployeeLifecycleItem.is_complete.is_(True),
    ).all():
        entries.append({
            "type": "lifecycle", "subtype": i.phase, "date": i.completed_date, "author": i.completed_by,
            "text": f"{i.phase.capitalize()} step completed: {i.label}.", "path": f"/employees/{employee_id}",
        })

    for e in db.query(AuditLog).filter(AuditLog.module_name == "employees", AuditLog.record_id == employee_id).all():
        entries.append({
            "type": "audit", "subtype": e.action, "date": e.created_at, "author": None,
            "text": _describe_employee_audit(e), "path": f"/employees/{employee_id}",
        })

    entries.sort(key=lambda e: e["date"] or datetime.min, reverse=True)
    for e in entries:
        e["date"] = e["date"].isoformat() if e["date"] else None

    return {
        "employee_id": employee_id, "employee_name": employee.name,
        "total_entries": len(entries),
        "entries": entries[:limit],
        "generated_at": datetime.utcnow().isoformat(),
    }


def employee_overview(db: Session, employee_id: int, is_privileged: bool,
                       can_view_documents: bool = True) -> Optional[dict]:
    """Section 13.1 - the Employee 360 Overview tab's single
    aggregation call: profile essentials plus concise summaries across
    attendance, work, leave, documents, and onboarding progress, each
    drawn from its own authoritative existing source. Salary/cost
    figures are included only when is_privileged (master or the
    employee's own profile), matching the confidentiality rule already
    used for the plain employee record (see _serialize_employees).

    can_view_documents separately gates document-derived facts
    (count, expiring-document exceptions) to master-only callers -
    stricter than is_privileged, matching the Documents API's own
    master-only rule for the "employee" parent type (see
    documents/api.py's SENSITIVE_PARENT_TYPES, which does not grant an
    exception even for an employee's own documents)."""
    from app.modules.documents.api import GenericDocument

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    documents_count = None
    if can_view_documents:
        documents_count = db.query(GenericDocument).filter(
            GenericDocument.parent_type == "employee", GenericDocument.parent_id == employee_id,
        ).count()
    onboarding = employee_lifecycle(db, employee_id, "onboarding")
    onboarding_complete = sum(1 for i in onboarding["items"] if i["is_complete"]) if onboarding else 0
    onboarding_total = len(onboarding["items"]) if onboarding else 0

    overview = {
        "label": "FACT",
        "profile": {
            "id": employee.id, "employee_code": employee.employee_code, "business_id": employee.business_id,
            "name": employee.name, "designation": employee.designation, "department": employee.department,
            "employment_status": employee.status, "phone": employee.phone, "email": employee.email,
            "manager": employee.manager,
            "joining_date": employee.joining_date.isoformat() if employee.joining_date else None,
            "exit_date": employee.exit_date.isoformat() if employee.exit_date else None,
            "exit_reason": employee.exit_reason,
        },
        "work_summary": employee_work_intelligence(db, employee_id),
        "attendance_summary": employee_attendance_intelligence(db, employee_id, months=1),
        "leave_summary": employee_leave_summary(db, employee_id),
        "documents_count": documents_count,
        "onboarding_progress": {"complete": onboarding_complete, "total": onboarding_total},
        "needs_attention": employee_needs_attention(db, employee_id, can_view_documents=can_view_documents),
    }
    if is_privileged:
        overview["salary_summary"] = {
            "monthly_salary": float(employee.monthly_salary or 0), "daily_wage": employee.daily_wage,
        }
        overview["cost_contribution"] = employee_cost_contribution(db, employee_id)
    return overview


# --- imports/holiday_schemas.py ---
class HolidayImportRowPreview(BaseModel):
    row_number: int
    date: Optional[str] = None
    name: Optional[str] = None
    is_working: Optional[bool] = None
    remarks: Optional[str] = None
    is_duplicate: bool = False
    errors: List[str] = []


class HolidayImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    rows: List[HolidayImportRowPreview]


class HolidayImportCommitRow(BaseModel):
    date: str
    name: str
    is_working: bool
    remarks: Optional[str] = None
    skip: bool = False
    # If true, an existing holiday on this date is updated (name/type/
    # remarks) rather than treated as an error - lets the same
    # export -> edit -> import round trip that other importers support
    # also work for holidays.
    overwrite_existing: bool = False


class HolidayImportCommitRequest(BaseModel):
    rows: List[HolidayImportCommitRow]


class HolidayImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    error: Optional[str] = None


# --- imports/holiday_import.py ---
"""Excel import for Company Holidays. Same discipline as app/modules/inventory/imports.py: one
fixed template shared by the download and the parser, never writes a
parsed row directly to the database (preview/commit are two separate
steps). Simpler than the Material/Product importers since there's no
catalog to fuzzy-match against - a holiday is identified by its date,
and the only duplicate concern is an exact date collision, which is
already how create_holiday/update_holiday enforce uniqueness (one
calendar override per date).
"""

TEMPLATE_VERSION = "1.0"


HOLIDAY_IMPORT_COLUMNS = ["Date *", "Holiday Name *", "Type *", "Remarks"]


HEADER_ALIASES = {
    "date": "Date *",
    "holiday name": "Holiday Name *",
    "name": "Holiday Name *",
    "holiday": "Holiday Name *",
    "type": "Type *",
    "remarks": "Remarks",
    "notes": "Remarks",
}


for _col in HOLIDAY_IMPORT_COLUMNS:
    HEADER_ALIASES.setdefault(_col.lower(), _col)
    HEADER_ALIASES.setdefault(_col.rstrip(" *").lower(), _col)


TYPE_TO_IS_WORKING = {"holiday": False, "special working day": True}


EXAMPLE_ROWS = [
    {"Date *": "2026-08-15", "Holiday Name *": "Independence Day", "Type *": "Holiday", "Remarks": ""},
    {"Date *": "2026-08-09", "Holiday Name *": "Special working Sunday - order backlog",
     "Type *": "Special Working Day", "Remarks": "Declared working to catch up on pending orders"},
]


def build_import_template() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, sheet_name="Company Holidays", title="Woodful Creations - Company Holiday Import Template",
        subtitle="Date, Holiday Name, and Type are required for every row (marked with *). "
                  "Each date can only have one calendar override - a date that's already a holiday "
                  "will be flagged during preview, not silently overwritten. Do not change the column headers.",
        columns=HOLIDAY_IMPORT_COLUMNS, rows=EXAMPLE_ROWS,
    )
    write_instructions_sheet(
        wb, template_name="Woodful Company Holiday Import Template", version=TEMPLATE_VERSION,
        field_docs=[
            {"name": "Date *", "mandatory": True, "meaning": "The calendar date this override applies to.",
             "format": "YYYY-MM-DD, e.g. 2026-08-15. One row per date."},
            {"name": "Holiday Name *", "mandatory": True, "meaning": "A short label for the date.",
             "format": "Free text, e.g. 'Independence Day'."},
            {"name": "Type *", "mandatory": True,
             "meaning": "Whether this date removes a working day (Holiday) or adds one back (Special Working Day).",
             "format": "Must be exactly 'Holiday' or 'Special Working Day'."},
            {"name": "Remarks", "mandatory": False, "meaning": "Optional free text note.", "format": "Free text."},
        ],
        duplicate_rule="Each date can only appear once, matching the app's own rule (one calendar "
                        "override per date) - importing a date that already exists as a holiday will "
                        "be flagged during preview, not silently overwritten.",
        extra_notes=[
            "A completely blank row is skipped. A row with only some fields filled in is still "
            "validated - if Date, Holiday Name, or Type is missing, that row will show an error.",
        ],
    )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _normalize_header_cell(raw) -> Optional[str]:
    if raw is None:
        return None
    key = re.sub(r"\s+", " ", str(raw).strip().lower())
    return HEADER_ALIASES.get(key)


def parse_uploaded_workbook(file_bytes: bytes) -> List[dict]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    enforce_workbook_row_limit(wb)
    ws = wb.worksheets[0]

    header_row_idx = None
    col_map = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        values = [c.value for c in row]
        candidate = {}
        ambiguous = False
        for idx, raw in enumerate(values):
            canonical = _normalize_header_cell(raw)
            if canonical:
                if canonical in candidate:
                    # A genuinely duplicated
                    # required header makes this row ambiguous, not
                    # resolvable. Matches the established convention
                    # already used by every other importer in this app
                    # (client/material/product/purchase/estimate/order/
                    # rate_card_import.py all reject the same way) -
                    # this file previously let the last occurrence
                    # silently win, which was the one inconsistent
                    # implementation, found and fixed via that
                    # cross-importer comparison.
                    ambiguous = True
                    break
                candidate[canonical] = idx
        if ambiguous:
            continue
        if {"Date *", "Holiday Name *", "Type *"}.issubset(candidate.keys()):
            header_row_idx = row[0].row
            col_map = candidate
            break

    if header_row_idx is None:
        raise ValueError(
            "Couldn't find the expected column headers in this file. "
            "Please use the downloaded template, or make sure Date, Holiday Name, and Type "
            "have a recognizable header."
        )

    rows = []
    for raw_row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
        if all(v is None for v in raw_row):
            continue
        row = {}
        for canonical, idx in col_map.items():
            row[canonical] = raw_row[idx] if idx < len(raw_row) else None
        rows.append(row)
    return rows


def validate_row(row: dict, existing_dates: set, seen_dates_in_file: set) -> tuple:
    """Returns (parsed_fields_dict, errors_list). parsed_fields_dict is
    always returned (even with errors) so the preview can show
    whatever was readable; errors indicate this row must not be
    committed as-is."""
    errors = []
    raw_date = row.get("Date *")
    parsed_date = None
    if raw_date in (None, ""):
        errors.append("Date is required")
    else:
        if isinstance(raw_date, datetime):
            parsed_date = raw_date.date()
        else:
            try:
                parsed_date = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Date must be in YYYY-MM-DD format, got {raw_date!r}")

    name = (row.get("Holiday Name *") or "").strip() if row.get("Holiday Name *") else ""
    if not name:
        errors.append("Holiday Name is required")

    raw_type = (row.get("Type *") or "").strip().lower() if row.get("Type *") else ""
    is_working = TYPE_TO_IS_WORKING.get(raw_type)
    if raw_type and is_working is None:
        errors.append(f"Type must be 'Holiday' or 'Special Working Day', got {row.get('Type *')!r}")
    elif not raw_type:
        errors.append("Type is required")

    is_duplicate = False
    if parsed_date is not None:
        if parsed_date in existing_dates:
            is_duplicate = True
        if parsed_date in seen_dates_in_file:
            errors.append(f"Duplicate date within this file: {parsed_date.isoformat()}")
        seen_dates_in_file.add(parsed_date)

    return (
        {
            "date": parsed_date.isoformat() if parsed_date else None,
            "name": name or None,
            "is_working": is_working,
            "remarks": (row.get("Remarks") or None),
            "is_duplicate": is_duplicate,
        },
        errors,
    )
