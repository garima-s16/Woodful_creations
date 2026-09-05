"""Chatbot HR-domain query/action handlers - employee/leave/task/
salary lookups, employee-add and task-assign/complete actions, and
the shared employee-name resolution helpers. Split out of the former
monolithic chat_service.py - see chat_inventory.py's docstring for
why."""
import re
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.modules.hr.models import Employee, Leave
from app.modules.operations.models import DailyTask
from app.modules.auth.models import User
from app.modules.communications.services.notification_service import NotificationService
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.ai.schemas import ChatContext, ProposedAction

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

    from app.modules.operations.api.daily_tasks import apply_task_completion
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
                from app.modules.communications.services.email_service import EmailService
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
