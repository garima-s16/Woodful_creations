"""Operations domain API routes (non-production): daily tasks,
issues, milestones, project expenses, work centres, and exports.
Combines the former daily_tasks.py, issues.py, milestones.py,
project_expenses.py, work_centres.py, and reports.py."""
from typing import List, Optional
from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.modules.operations.models import DailyTask, TaskComment
from app.modules.sales.models import Order, OrderItem
from app.modules.auth.auth import User
from app.modules.hr.models import Employee
from app.modules.communications.services import NotificationService
from app.modules.communications.services import notify_mentions
from app.modules.operations.schemas import DailyTaskCreate, DailyTaskUpdate, DailyTaskResponse, CompleteAndAssignNext, TaskCommentCreate, TaskCommentResponse
from app.platform.ids import generate_unique_code, generate_business_id
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.modules.operations.models import Issue
from app.modules.operations.schemas import IssueCreate, IssueResponse
from app.modules.inventory.services import StockService
from app.platform.audit import log_action
from app.modules.operations.models import Milestone
from app.modules.sales.models import Order
from app.modules.operations.schemas import MilestoneCreate, MilestoneUpdate, MilestoneResponse
from app.platform.ids import generate_business_id
from app.platform.security import require_role
from app.platform.audit import log_action, serializable_fields
from app.modules.operations.models import ProjectExpense
from app.modules.operations.schemas import ProjectExpenseCreate, ProjectExpenseUpdate, ProjectExpenseResponse
from app.modules.operations.models import WorkCentre
from app.modules.operations.schemas import WorkCentreCreate, WorkCentreUpdate, WorkCentreResponse
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from app.platform.security import rate_limit
from app.platform.config import settings
from app.modules.operations.models import DailyTask, ProductionJob
from app.modules.communications.models import AutomationLog
from app.shared import build_workbook, xlsx_response


# --- daily_tasks.py ---
daily_tasks_router = APIRouter(prefix="/api/daily-tasks", tags=["daily-tasks"])


def _validate_order_item(db: Session, order_id: Optional[int], order_item_id: Optional[int]):
    """An Order Item, when given, must actually belong to the given
    Order - reuses the existing Order/OrderItem relationship rather than
    trusting an unrelated id."""
    if order_item_id is None:
        return
    item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    if order_id and item.order_id != order_id:
        raise HTTPException(status_code=400, detail="Order item does not belong to the selected order")


def _serialize_task(db: Session, task: DailyTask, at_risk_order_ids: set = None) -> DailyTaskResponse:
    """Attaches read-only client/order/product/employee context, always
    derived live from the existing relationships - never stored on
    DailyTask itself."""
    response = DailyTaskResponse.model_validate(task)
    if task.employee:
        response.employee_name = task.employee.name
    if task.order:
        response.order_code = task.order.order_code
        if task.order.client:
            response.client_name = task.order.client.name
    if task.order_item:
        response.product_name = task.order_item.product_name or task.order_item.description
    if at_risk_order_ids is not None and task.order_id in at_risk_order_ids:
        response.material_at_risk = True
    return response


def _serialize_tasks(db: Session, tasks, include_material_risk: bool = False) -> List[DailyTaskResponse]:
    """include_material_risk computes the at-risk order set once for
    the whole page (StockService.calculate_at_risk_orders is already a
    bounded, business-wide calculation regardless of how many orders
    exist - see its own docstring) - opt-in, since most callers of this
    list (e.g. the dashboard's small "my tasks" widget) have no use for
    it and should not pay for the extra queries on every call."""
    at_risk_order_ids = None
    if include_material_risk:
        from app.modules.inventory.services import StockService
        at_risk_order_ids = {row["order_id"] for row in StockService.calculate_at_risk_orders(db)}
    return [_serialize_task(db, t, at_risk_order_ids) for t in tasks]


def _build_task_assignment_email(task_response: DailyTaskResponse) -> tuple:
    """The task email's actual content, built
    entirely from real values already resolved onto task_response by
    _serialize_task (client_name/order_code/product_name), never
    invented. Returns (subject, body); the frontend origin for the
    link is not known here, so a relative path is included - matches
    the same action_path convention already used for in-app
    notifications elsewhere in this file."""
    subject = f"Task Assigned: {task_response.task_code}"
    lines = [
        f"Task ID: {task_response.task_code}",
        f"Work: {task_response.task_description}",
    ]
    if task_response.client_name:
        lines.append(f"Client: {task_response.client_name}")
    if task_response.order_code:
        lines.append(f"Order: {task_response.order_code}")
    if task_response.product_name:
        lines.append(f"Product: {task_response.product_name}")
    if task_response.due_date:
        lines.append(f"Due Date: {task_response.due_date.strftime('%d %b %Y')}")
    if task_response.priority:
        lines.append(f"Priority: {task_response.priority}")
    lines.append(f"Status: {task_response.status}")
    lines.append(f"\nOpen this task: /daily-tasks/{task_response.id}")
    return subject, "\n".join(lines)


@daily_tasks_router.get("/", response_model=List[DailyTaskResponse])
def list_daily_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                      order_item_id: Optional[int] = Query(None),
                      date: Optional[datetime] = Query(None), status: Optional[str] = Query(None),
                      exclude_status: Optional[str] = Query(None),
                      task_category: Optional[str] = Query(None), priority: Optional[str] = Query(None),
                      due_date_from: Optional[datetime] = Query(None), due_date_to: Optional[datetime] = Query(None),
                      overdue: bool = Query(False),
                      mine: bool = Query(False),
                      include_material_risk: bool = Query(False),
                      limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                      db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(DailyTask).options(
        joinedload(DailyTask.employee),
        joinedload(DailyTask.order).joinedload(Order.client),
        joinedload(DailyTask.order_item),
    )
    if mine:
        my_employee_id = auth.get("employee_id")
        if my_employee_id is None:
            raise HTTPException(status_code=400, detail="Your account is not linked to an employee record.")
        query = query.filter(DailyTask.employee_id == my_employee_id)
    elif employee_id:
        query = query.filter(DailyTask.employee_id == employee_id)
    if order_id:
        query = query.filter(DailyTask.order_id == order_id)
    if order_item_id:
        query = query.filter(DailyTask.order_item_id == order_item_id)
    if date:
        query = query.filter(DailyTask.date == date)
    if status:
        query = query.filter(DailyTask.status == status)
    if exclude_status:
        # Dashboard "my tasks" summary widget - was previously
        # dailyTasksAPI.list({mine: true}) with no status filter at
        # all (every task ever assigned to this employee, DONE or
        # not, forever) just to compute 4 counts, none of which need
        # DONE tasks. A direct field filter removes exactly the
        # unbounded historical component.
        query = query.filter(DailyTask.status != exclude_status)
    if task_category:
        query = query.filter(DailyTask.task_category == task_category)
    if priority:
        query = query.filter(DailyTask.priority == priority)
    if due_date_from:
        query = query.filter(DailyTask.due_date >= due_date_from)
    if due_date_to:
        query = query.filter(DailyTask.due_date <= due_date_to)
    if overdue:
        query = query.filter(DailyTask.due_date < datetime.utcnow(), DailyTask.status != "DONE")
    tasks_query = query.order_by(DailyTask.date.desc())
    if limit is not None:
        # Optional and unbounded by default on purpose -
        # DailyTasksPage renders the full list with no client-side
        # pagination of its own, so a default limit here would
        # silently truncate that page. Only callers that explicitly
        # ask (the dashboard) get a bounded result.
        tasks_query = tasks_query.offset(offset).limit(limit)
    tasks = tasks_query.all()
    return _serialize_tasks(db, tasks, include_material_risk=include_material_risk)


@daily_tasks_router.post("/", response_model=DailyTaskResponse, status_code=201)
def create_daily_task(data: DailyTaskCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Task creation/assignment is a management operation - only Master
    can assign work. Normal users cannot arbitrarily
    assign tasks to themselves or others."""
    payload = data.dict(exclude={"task_code", "due_date"})
    if not payload.get("created_by"):
        payload["created_by"] = auth.get("email")

    _validate_order_item(db, payload.get("order_id"), payload.get("order_item_id"))

    # Due date inherits from the Order's overall
    # delivery date by default; an explicitly supplied due_date becomes
    # an authoritative task-specific override instead.
    due_date_overridden = False
    due_date = data.due_date
    if due_date is not None:
        due_date_overridden = True
    elif payload.get("order_id"):
        order = db.query(Order).filter(Order.id == payload["order_id"]).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        due_date = order.delivery_date

    for _ in range(5):
        code = generate_unique_code(db, DailyTask, "task_code", "TSK-")
        task = DailyTask(
            **payload, task_code=code, business_id=generate_business_id(db),
            due_date=due_date, due_date_overridden=due_date_overridden,
        )
        db.add(task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(task)
        if task.employee_id:
            task_response = _serialize_task(db, task)
            employee = task.employee
            recipient = db.query(User).filter(User.employee_id == task.employee_id).first()
            if recipient:
                email_subject, email_body = _build_task_assignment_email(task_response)
                NotificationService.notify(
                    db, notification_type="TASK_ASSIGNED", severity="INFO",
                    title="New task assigned", message=f"{task.task_description}",
                    recipient_user_id=recipient.id, related_entity_type="task",
                    related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                    recipient_email=employee.email if employee else None,
                    email_subject=email_subject, email_body=email_body,
                )
            elif employee and employee.email:
                # No linked login, so no in-app notification (there is
                # no one to sign in and see it) - but the employee
                # still has a real email on file, and the
                # requirement is about the employee's email, not about
                # having a login.
                email_subject, email_body = _build_task_assignment_email(task_response)
                try:
                    from app.modules.communications.services import EmailService
                    EmailService().send_email(to_email=employee.email, subject=email_subject, body=email_body, is_html=False)
                except Exception as e:
                    logging.getLogger(__name__).error(f"Task assignment email failed for {employee.email}: {e}")
        return _serialize_task(db, task)
    raise HTTPException(status_code=500, detail="Unable to generate a unique task code, please try again")


@daily_tasks_router.get("/{task_id}", response_model=DailyTaskResponse)
def get_daily_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    task = db.query(DailyTask).options(
        joinedload(DailyTask.employee),
        joinedload(DailyTask.order).joinedload(Order.client),
        joinedload(DailyTask.order_item),
    ).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_task(db, task)


@daily_tasks_router.post("/{task_id}/send-email")
def send_task_email(task_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """On-demand task email - distinct from the automatic
    create/reassign triggers (already wired). Reuses
    the exact same content-building helper those use, so the email a
    Master explicitly requests is never different from what gets sent
    automatically."""
    task = db.query(DailyTask).options(
        joinedload(DailyTask.employee),
        joinedload(DailyTask.order).joinedload(Order.client),
        joinedload(DailyTask.order_item),
    ).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.employee_id or not task.employee or not task.employee.email:
        raise HTTPException(status_code=400, detail="This task has no assigned employee with an email on file.")

    task_response = _serialize_task(db, task)
    subject, body = _build_task_assignment_email(task_response)
    from app.modules.communications.services import EmailService
    sent = EmailService().send_email(to_email=task.employee.email, subject=subject, body=body, is_html=False)

    from app.platform.audit import log_action
    log_action(db, request, user_id=auth.get("user_id"), action="send_task_email",
               module_name="daily_tasks", record_id=task.id,
               new_value={"recipient": task.employee.email, "sent": sent})

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="The task email could not be sent right now (email service unavailable or misconfigured). "
                   "The task itself is unaffected.",
        )
    return {"sent": True, "message": f"Task details emailed to {task.employee.name}."}


@daily_tasks_router.post("/send-team-summary-email")
def send_team_summary_email(request: Request, task_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
                             db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The team-level assignment overview
    every master receives after task assignment is done for the day,
    distinct from each employee's own individual email -
    employees never see other employees' tasks; this summary is
    master-only content.

    Sent to every active master user (not just whoever triggered it),
    per explicit correction: masters should all stay aware of the
    team's daily assignments, regardless of who happened to ask for
    the summary. Any master user may trigger this - there is no
    single hardcoded "the founder" recipient."""
    from app.modules.operations.models import DailyTask
    from app.modules.hr.models import Employee
    master_emails = [
        u.email for u in db.query(User).filter(User.role == "master", User.is_active == True).all()  # noqa: E712
        if u.email
    ]
    if not master_emails:
        raise HTTPException(status_code=400, detail="No active master account has an email on file.")

    if task_date:
        try:
            target_date = datetime.strptime(task_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="task_date must be in YYYY-MM-DD format.")
    else:
        target_date = datetime.utcnow().date()

    from sqlalchemy import func as _func
    tasks = (
        db.query(DailyTask).options(joinedload(DailyTask.employee))
        .join(Employee, DailyTask.employee_id == Employee.id)
        .filter(_func.date(DailyTask.date) == target_date)
        .order_by(Employee.name, DailyTask.id).all()
    )
    if not tasks:
        raise HTTPException(status_code=404, detail=f"No tasks are assigned for {target_date.strftime('%d %b %Y')}.")

    by_employee: dict = {}
    for t in tasks:
        name = t.employee.name if t.employee else "Unassigned"
        by_employee.setdefault(name, []).append(t)

    lines = [f"Woodful Team Task Summary - {target_date.strftime('%d %b %Y')}", ""]
    for name, employee_tasks in by_employee.items():
        lines.append(f"{name}:")
        for t in employee_tasks:
            lines.append(f"  - [{t.task_code}] {t.task_description} (Status: {t.status})")
        lines.append("")
    body = "\n".join(lines)
    subject = f"Woodful Team Task Summary - {target_date.strftime('%d %b %Y')}"

    from app.modules.communications.services import EmailService
    email_service = EmailService()
    results = {email: email_service.send_email(to_email=email, subject=subject, body=body, is_html=False)
               for email in master_emails}
    sent_count = sum(1 for ok in results.values() if ok)

    from app.platform.audit import log_action
    log_action(db, request, user_id=auth.get("user_id"), action="send_team_summary_email",
               module_name="daily_tasks",
               new_value={"recipients": master_emails, "sent_count": sent_count, "task_count": len(tasks)})

    if sent_count == 0:
        raise HTTPException(
            status_code=502,
            detail="The team summary could not be sent right now (email service unavailable or misconfigured).",
        )
    failed = [email for email, ok in results.items() if not ok]
    message = f"Team summary ({len(tasks)} task(s)) emailed to {sent_count} of {len(master_emails)} master account(s)."
    if failed:
        message += f" Failed for: {', '.join(failed)}."
    return {"sent": True, "message": message, "task_count": len(tasks), "sent_count": sent_count, "failed_recipients": failed}


def apply_task_completion(task: DailyTask) -> None:
    """The canonical "mark this task done" logic -
    sets status, completion_percent, and actual_completed_at
    consistently. actual_completed_at is only stamped on the genuine
    transition INTO "DONE" (never overwritten on a task that was
    already done).

    Used directly by ChatService's task-completion action, which
    previously set task.status/completion_percent by hand and never
    touched actual_completed_at at all - that was the actual defect.
    update_daily_task below implements the identical behavior inline
    (verified to match exactly) rather than calling this function
    directly, since its own version is entangled with status_changed's
    timing-sensitive computation (used for this same route's
    reassignment-notification logic further down) - touching that
    working code isn't necessary to fix the defect, which was entirely
    that the chatbot never reached equivalent logic in the first
    place."""
    if task.status != "DONE":
        task.actual_completed_at = datetime.utcnow()
    task.status = "DONE"
    task.completion_percent = 100


EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "completion_percent", "delay_reason", "remarks"}


@daily_tasks_router.put("/{task_id}", response_model=DailyTaskResponse)
def update_daily_task(task_id: int, data: DailyTaskUpdate, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    # Locked before checking/setting status - see complete_and_assign_next
    # for why: two simultaneous updates to the same task (a double-submit
    # marking it DONE) must not both read the same pre-update status and
    # each fire their own "status changed" notification.
    task = db.query(DailyTask).options(
        joinedload(DailyTask.employee),
        joinedload(DailyTask.order).joinedload(Order.client),
        joinedload(DailyTask.order_item),
    ).filter(DailyTask.id == task_id).with_for_update().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    role = auth.get("role", "user")
    update_data = data.dict(exclude_unset=True)

    if role not in ("master",):
        # Ownership is resolved via the authenticated user's linked
        # Employee record, never by comparing names:
        # "authenticated user -> employee_id -> DailyTask.employee_id".
        if task.employee_id != auth.get("employee_id"):
            raise HTTPException(status_code=403, detail="You can only update your own assigned tasks.")
        disallowed = set(update_data.keys()) - EMPLOYEE_SELF_SERVICE_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"You can only update: {', '.join(sorted(EMPLOYEE_SELF_SERVICE_FIELDS))}. "
                       f"Not allowed to change: {', '.join(sorted(disallowed))}.",
            )
    else:
        new_order_id = update_data.get("order_id", task.order_id)
        new_order_item_id = update_data.get("order_item_id", task.order_item_id)
        if "order_item_id" in update_data or "order_id" in update_data:
            _validate_order_item(db, new_order_id, new_order_item_id)
        if "due_date" in update_data:
            # A Master explicitly setting/clearing the due date is always
            # an override - it must not be silently replaced the next
            # time the parent Order's delivery_date changes.
            update_data["due_date_overridden"] = update_data["due_date"] is not None
        elif "order_id" in update_data and new_order_id != task.order_id and not task.due_date_overridden:
            # Changing the Order
            # itself, without an explicit due_date in the same request,
            # must still refresh an inherited due date to the new
            # order's delivery date - matching the same inheritance
            # behavior applied at task creation. An explicit override
            # (due_date_overridden=True) is left untouched here.
            if new_order_id:
                new_order = db.query(Order).filter(Order.id == new_order_id).first()
                if not new_order:
                    raise HTTPException(status_code=404, detail="Order not found")
                update_data["due_date"] = new_order.delivery_date
            else:
                update_data["due_date"] = None

    if update_data.get("status") == "DONE":
        update_data["completion_percent"] = 100
        if task.status != "DONE":
            update_data["actual_completed_at"] = datetime.utcnow()

    status_changed = "status" in update_data and update_data["status"] != task.status
    reassigned = "employee_id" in update_data and update_data["employee_id"] != task.employee_id
    new_employee_id = update_data.get("employee_id", task.employee_id)

    for field, value in update_data.items():
        setattr(task, field, value)
    db.add(task)
    db.commit()
    db.refresh(task)

    if reassigned and new_employee_id:
        recipient = db.query(User).filter(User.employee_id == new_employee_id).first()
        new_employee = db.query(Employee).filter(Employee.id == new_employee_id).first()
        task_response = _serialize_task(db, task)
        if recipient:
            email_subject, email_body = _build_task_assignment_email(task_response)
            NotificationService.notify(
                db, notification_type="TASK_ASSIGNED", severity="INFO",
                title="Task reassigned to you", message=f"{task.task_description}",
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                recipient_email=new_employee.email if new_employee else None,
                email_subject=email_subject, email_body=email_body,
            )
        elif new_employee and new_employee.email:
            email_subject, email_body = _build_task_assignment_email(task_response)
            try:
                from app.modules.communications.services import EmailService
                EmailService().send_email(to_email=new_employee.email, subject=email_subject, body=email_body, is_html=False)
            except Exception as e:
                logging.getLogger(__name__).error(f"Task reassignment email failed for {new_employee.email}: {e}")

    if status_changed and task.employee_id:
        recipient = db.query(User).filter(User.employee_id == task.employee_id).first()
        if recipient:
            is_blocked = task.status == "BLOCKED"
            NotificationService.notify(
                db, notification_type="TASK_BLOCKED" if is_blocked else "TASK_STATUS_CHANGED",
                severity="WARNING" if is_blocked else "INFO",
                title="Task blocked" if is_blocked else f"Task status: {task.status}",
                message=f"{task.task_description}",
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                dedup_key=f"task-status-{task.id}-{task.status}",
            )
        # A blocked task genuinely needs
        # management awareness to get unblocked, not just a ping to
        # the same employee who just marked it blocked. Every active
        # Master User is notified, not only whoever originally assigned
        # the task.
        if task.status == "BLOCKED":
            masters = db.query(User).filter(User.role == "master", User.is_active == True).all()  # noqa: E712
            for master in masters:
                if recipient and master.id == recipient.id:
                    continue
                NotificationService.notify(
                    db, notification_type="TASK_BLOCKED", severity="WARNING",
                    title="Task blocked", message=f"{task.task_description}",
                    recipient_user_id=master.id, related_entity_type="task",
                    related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                    dedup_key=f"task-blocked-master-{task.id}-{master.id}",
                )

    # If a task dependency is explicitly defined, completion should
    # enable the appropriate downstream workflow. parent_task_id is an
    # existing model/schema field never actively used anywhere until
    # now - dependencies must be explicitly set (this field), never
    # inferred from employee roles. A no-op for the vast
    # majority of tasks, which were never linked this way.
    if status_changed and task.status == "DONE":
        dependents = db.query(DailyTask).options(joinedload(DailyTask.employee)).filter(
            DailyTask.parent_task_id == task.id,
        ).all()
        for dependent in dependents:
            if not dependent.employee_id:
                continue
            dep_recipient = db.query(User).filter(User.employee_id == dependent.employee_id).first()
            if dep_recipient:
                NotificationService.notify(
                    db, notification_type="TASK_DEPENDENCY_READY", severity="INFO",
                    title="A task you were waiting on is now done",
                    message=f"\"{task.task_description}\" is complete - \"{dependent.task_description}\" can proceed.",
                    recipient_user_id=dep_recipient.id, related_entity_type="task",
                    related_entity_id=dependent.id, action_path=f"/daily-tasks/{dependent.id}",
                    dedup_key=f"task-dependency-ready-{dependent.id}-{task.id}",
                )
    return _serialize_task(db, task)


@daily_tasks_router.post("/{task_id}/complete-and-assign-next", response_model=DailyTaskResponse, status_code=201)
def complete_and_assign_next(task_id: int, data: CompleteAndAssignNext, db: Session = Depends(get_db),
                              auth=Depends(get_current_user)):
    """Completes the current task and creates a new, linked task for
    the next person - the original is never overwritten, so the full
    handoff chain (previous_task_id) stays intact. Order/Order Item
    context and due date carry over from the task being completed
    unless explicitly overridden in the request."""
    # Locked before checking status - two simultaneous requests for the
    # same task (a double-click on a slow connection, or two tabs) must
    # not both pass the DONE check and each create their own "next"
    # task - the second must see the first's completed status and be
    # rejected, not silently hand this task off twice.
    task = db.query(DailyTask).filter(DailyTask.id == task_id).with_for_update().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "DONE":
        raise HTTPException(status_code=409, detail="This task has already been completed.")

    role = auth.get("role", "user")
    if role not in ("master",) and task.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only complete and hand off your own tasks.")

    # Completing one's own task does not by
    # itself authorize assigning the NEXT task to someone else - that
    # is a separate operation, governed by the same rule
    # create_daily_task already enforces ("only master can assign work
    # to others" - see that endpoint's own docstring). A non-master
    # employee continuing their own task chain (assigning the next step
    # to themselves) is still allowed, since that is not directing
    # anyone else's work and preserves the legitimate handoff workflow.
    if role not in ("master",) and data.next_employee_id != auth.get("employee_id"):
        raise HTTPException(
            status_code=403,
            detail="Assigning the next task to another employee requires a master account. "
                   "You can still hand this off to yourself.",
        )

    task.status = "DONE"
    task.completion_percent = 100
    if task.actual_completed_at is None:
        task.actual_completed_at = datetime.utcnow()
    db.add(task)

    next_order_id = data.next_order_id if data.next_order_id is not None else task.order_id
    next_order_item_id = data.next_order_item_id if data.next_order_item_id is not None else task.order_item_id
    _validate_order_item(db, next_order_id, next_order_item_id)

    due_date_overridden = data.next_due_date is not None
    next_due_date = data.next_due_date
    if next_due_date is None:
        next_due_date = task.due_date
        due_date_overridden = task.due_date_overridden

    payload = {
        "date": datetime.utcnow(), "employee_id": data.next_employee_id, "order_id": next_order_id,
        "order_item_id": next_order_item_id, "task_description": data.next_task_description,
        "priority": data.next_priority, "created_by": auth.get("email"), "previous_task_id": task.id,
        "remarks": data.note, "due_date": next_due_date, "due_date_overridden": due_date_overridden,
    }
    for _ in range(5):
        code = generate_unique_code(db, DailyTask, "task_code", "TSK-")
        next_task = DailyTask(**payload, task_code=code, business_id=generate_business_id(db))
        db.add(next_task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(next_task)
        next_task_response = _serialize_task(db, next_task)
        next_employee = next_task.employee
        recipient = db.query(User).filter(User.employee_id == data.next_employee_id).first()
        if recipient:
            email_subject, email_body = _build_task_assignment_email(next_task_response)
            NotificationService.notify(
                db, notification_type="TASK_ASSIGNED", severity="INFO",
                title="Next action assigned", message=data.next_task_description,
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=next_task.id, action_path=f"/daily-tasks/{next_task.id}",
                recipient_email=next_employee.email if next_employee else None,
                email_subject=email_subject, email_body=email_body,
            )
        elif next_employee and next_employee.email:
            # Same fallback create_daily_task uses for an employee with
            # no linked login - still gets the real email even though
            # there's no in-app notification to deliver.
            email_subject, email_body = _build_task_assignment_email(next_task_response)
            try:
                from app.modules.communications.services import EmailService
                EmailService().send_email(to_email=next_employee.email, subject=email_subject, body=email_body, is_html=False)
            except Exception as e:
                logging.getLogger(__name__).error(f"Handoff task assignment email failed for {next_employee.email}: {e}")
        return next_task_response
    raise HTTPException(status_code=500, detail="Unable to generate a unique task code, please try again")


@daily_tasks_router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
def list_task_comments(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(DailyTask).filter(DailyTask.id == task_id).first():
        raise HTTPException(status_code=404, detail="Task not found")
    return db.query(TaskComment).filter(TaskComment.task_id == task_id).order_by(TaskComment.date.asc()).all()


@daily_tasks_router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
def add_task_comment(task_id: int, data: TaskCommentCreate, db: Session = Depends(get_db),
                      auth=Depends(get_current_user)):
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comment = TaskComment(
        task_id=task_id, author=auth.get("email") or "Unknown", text=data.text, date=datetime.utcnow(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    # @mentions in a task comment notify the mentioned user
    # directly (never a broadcast - a mention is addressed to one
    # person). Best-effort: a malformed/unmatched handle is simply not
    # notified, never a reason to fail the comment itself.
    notify_mentions(
        db, text=data.text, comment_id=comment.id, source_type="task_comment",
        entity_type="task", entity_id=task_id,
        title=f"Mentioned in task {task.task_code}", action_path=f"/daily-tasks/{task_id}",
        excluded_user_id=auth.get("user_id"),
    )
    return comment


# --- issues.py ---
issues_router = APIRouter(prefix="/api/issues", tags=["issues"])


@issues_router.get("/", response_model=List[IssueResponse])
def list_issues(order_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Issue)
    if order_id:
        query = query.filter(Issue.order_id == order_id)
    if material_id:
        query = query.filter(Issue.material_id == material_id)
    return query.order_by(Issue.date.desc()).all()


@issues_router.post("/", response_model=IssueResponse, status_code=201)
def create_issue(data: IssueCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return StockService.record_issue(db, data)


@issues_router.get("/{issue_id}", response_model=IssueResponse)
def get_issue(issue_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


# --- milestones.py ---
milestones_router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@milestones_router.get("/", response_model=List[MilestoneResponse])
def list_milestones(order_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(get_current_user)):
    query = db.query(Milestone)
    if order_id:
        query = query.filter(Milestone.order_id == order_id)
    return query.order_by(Milestone.target_date.asc()).all()


@milestones_router.post("/", response_model=MilestoneResponse, status_code=201)
def create_milestone(data: MilestoneCreate, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    milestone = Milestone(**data.dict(), business_id=generate_business_id(db))
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    log_action(db, request, user_id=auth.get("user_id"), action="create_milestone", module_name="milestones",
               record_id=milestone.id, new_value={"order_id": milestone.order_id, "name": milestone.name})
    return milestone


@milestones_router.put("/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(milestone_id: int, data: MilestoneUpdate, request: Request,
                      db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    old_value = {"name": milestone.name, "completed_date": str(milestone.completed_date)}
    for field, value in data.dict(exclude_unset=True).items():
        setattr(milestone, field, value)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    log_action(db, request, user_id=auth.get("user_id"), action="update_milestone", module_name="milestones",
               record_id=milestone.id, old_value=old_value,
               new_value={"name": milestone.name, "completed_date": str(milestone.completed_date)})
    return milestone


@milestones_router.delete("/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: int, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    old_value = {"order_id": milestone.order_id, "name": milestone.name}
    db.delete(milestone)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_milestone", module_name="milestones",
               record_id=milestone_id, old_value=old_value)


# --- project_expenses.py ---
project_expenses_router = APIRouter(prefix="/api/project-expenses", tags=["project-expenses"])


@project_expenses_router.get("/", response_model=List[ProjectExpenseResponse])
def list_project_expenses(order_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    query = db.query(ProjectExpense)
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
    return query.order_by(ProjectExpense.date.desc()).all()


@project_expenses_router.post("/", response_model=ProjectExpenseResponse, status_code=201)
def create_project_expense(data: ProjectExpenseCreate, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"expense_code"})
    for _ in range(5):
        code = generate_unique_code(db, ProjectExpense, "expense_code", "EXP-")
        expense = ProjectExpense(**payload, expense_code=code, business_id=generate_business_id(db))
        db.add(expense)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(expense)
        log_action(db, request, user_id=auth.get("user_id"), action="create_project_expense",
                   module_name="project_expenses", record_id=expense.id, new_value={
                       "order_id": expense.order_id, "category": expense.category,
                       "amount": float(expense.amount or 0),
                   })
        return expense
    raise HTTPException(status_code=500, detail="Unable to generate a unique expense code, please try again")


@project_expenses_router.get("/{expense_id}", response_model=ProjectExpenseResponse)
def get_project_expense(expense_id: int, db: Session = Depends(get_db),
                         auth=Depends(require_role("master"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@project_expenses_router.put("/{expense_id}", response_model=ProjectExpenseResponse)
def update_project_expense(expense_id: int, data: ProjectExpenseUpdate, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(expense, updates.keys())
    for field, value in updates.items():
        setattr(expense, field, value)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    log_action(db, request, user_id=auth.get("user_id"), action="update_project_expense",
               module_name="project_expenses", record_id=expense.id, old_value=old_value,
               new_value=serializable_fields(expense, updates.keys()))
    return expense


# --- work_centres.py ---
work_centres_router = APIRouter(prefix="/api/work-centres", tags=["work-centres"])


@work_centres_router.get("/", response_model=List[WorkCentreResponse])
def list_work_centres(active_only: bool = Query(False), db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(WorkCentre)
    if active_only:
        query = query.filter(WorkCentre.is_active.is_(True))
    return query.order_by(WorkCentre.name).all()


@work_centres_router.post("/", response_model=WorkCentreResponse, status_code=201)
def create_work_centre(data: WorkCentreCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    for _ in range(5):
        centre = WorkCentre(**data.dict(), business_id=generate_business_id(db))
        db.add(centre)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.query(WorkCentre).filter(WorkCentre.name == data.name).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"A work centre named \"{data.name}\" already exists.")
            continue
        db.refresh(centre)
        return centre
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@work_centres_router.get("/{work_centre_id}", response_model=WorkCentreResponse)
def get_work_centre(work_centre_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    return centre


@work_centres_router.put("/{work_centre_id}", response_model=WorkCentreResponse)
def update_work_centre(work_centre_id: int, data: WorkCentreUpdate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(centre, field, value)
    db.add(centre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"A work centre named \"{data.name}\" already exists.")
    db.refresh(centre)
    return centre


@work_centres_router.get("/{work_centre_id}/capacity")
def get_work_centre_capacity(work_centre_id: int, date: Optional[str] = Query(None),
                              db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """P0.3.6 - real capacity awareness: sums estimated_duration_minutes
    of every operation actually assigned to this work centre on the
    given date (via start_time's date), compares against the work
    centre's own configured capacity_hours_per_day. Never claims a
    conflict without real, existing scheduled operations behind it."""
    from datetime import datetime as dt
    from app.modules.operations.models import ProductionOperation

    centre = db.query(WorkCentre).filter(WorkCentre.id == work_centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Work centre not found")
    if centre.capacity_hours_per_day is None:
        return {
            "work_centre_id": work_centre_id, "has_capacity_data": False,
            "message": "No daily capacity is configured for this work centre.",
        }

    target_date = dt.fromisoformat(date).date() if date else dt.utcnow().date()
    operations = db.query(ProductionOperation).filter(
        ProductionOperation.work_centre_id == work_centre_id,
        ProductionOperation.status != "Completed",
    ).all()
    scheduled_minutes = sum(
        (op.estimated_duration_minutes or 0) for op in operations
        if op.start_time and op.start_time.date() == target_date
    )
    capacity_minutes = float(centre.capacity_hours_per_day) * 60
    remaining_minutes = capacity_minutes - scheduled_minutes

    return {
        "work_centre_id": work_centre_id, "has_capacity_data": True, "date": target_date.isoformat(),
        "capacity_minutes": capacity_minutes, "scheduled_minutes": scheduled_minutes,
        "remaining_minutes": remaining_minutes,
        "status": "CAPACITY_CONFLICT" if remaining_minutes < 0 else "OK",
    }


# --- reports.py ---
"""Operations-domain report exports: production jobs, daily tasks,
project expenses, the automation audit log, and the daily status
report (Excel + email delivery). Split out of the former monolithic
reports.py - see modules/inventory/api/reports.py's docstring for why."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/production.xlsx")
def export_production(
    employee_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
    order_id: Optional[int] = Query(None), stage: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """One flexible, filterable endpoint covering "Production Jobs",
    "Daily/Weekly Production" (via date_from/date_to), and
    "Machine/Operator Work" (via machine/employee_id) - all genuinely
    the same underlying ProductionJob data with a different filter
    applied, matching the export_tasks precedent rather than
    proliferating near-duplicate routes for each named variant."""
    query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        query = query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Operator: {employee.name if employee else employee_id}")
    if machine:
        query = query.filter(ProductionJob.machine == machine)
        filters_applied.append(f"Machine: {machine}")
    if order_id:
        query = query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if stage:
        query = query.filter(ProductionJob.stage == stage)
        filters_applied.append(f"Stage: {stage}")
    if date_from:
        query = query.filter(ProductionJob.date >= date_from)
        filters_applied.append(f"From: {date_from.strftime('%d-%m-%Y')}")
    if date_to:
        query = query.filter(ProductionJob.date <= date_to)
        filters_applied.append(f"To: {date_to.strftime('%d-%m-%Y')}")

    jobs = query.order_by(ProductionJob.date.desc()).all()
    rows = [{
        "job_id": j.business_id or "", "date": j.date.strftime("%d-%m-%Y") if j.date else "",
        "operator": j.employee.name if j.employee else "", "order": j.order.order_code if j.order else "",
        "machine": j.machine or "", "stage": j.stage or "", "operation": j.operation or "",
        "planned_qty": j.planned_qty, "completed_qty": j.completed_qty, "status": j.status,
        "completion_date": j.completion_date.strftime("%d-%m-%Y") if j.completion_date else "",
        "remarks": j.remarks or "",
    } for j in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Jobs", str(len(jobs))),
        ("Completed", str(sum(1 for j in jobs if j.status == "Completed"))),
        ("Total Planned Qty", str(sum(j.planned_qty for j in jobs))),
        ("Total Completed Qty", str(sum(j.completed_qty for j in jobs))),
    ]

    buffer = build_workbook([{
        "sheet_name": "Production", "title": "PRODUCTION REPORT",
        "columns": ["job_id", "date", "operator", "order", "machine", "stage", "operation",
                    "planned_qty", "completed_qty", "status", "completion_date", "remarks"],
        "headers": ["Job ID", "Date", "Operator", "Order", "Machine", "Stage", "Operation",
                    "Planned Qty", "Completed Qty", "Status", "Completion Date", "Remarks"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/tasks.xlsx")
def export_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Tasks & Production export - no financial fields exist on either
    model, so no role-based redaction is needed, matching "everyone can
    view tasks" for the Tasks sheet. employee_id covers "Employee-wise
    Tasks Excel", order_id covers "Project Tasks Excel" - one flexible,
    filterable endpoint rather than three separate routes for what's
    the same underlying data with a different filter applied."""
    task_query = db.query(DailyTask).options(
        selectinload(DailyTask.employee), selectinload(DailyTask.order), selectinload(DailyTask.order_item),
    )
    job_query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        task_query = task_query.filter(DailyTask.employee_id == employee_id)
        job_query = job_query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if order_id:
        task_query = task_query.filter(DailyTask.order_id == order_id)
        job_query = job_query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")

    tasks = task_query.order_by(DailyTask.date.desc()).all()
    task_rows = [{
        "task_id": t.business_id or "", "date": t.date.strftime("%d-%m-%Y") if t.date else "",
        "employee": t.employee.name if t.employee else "", "task": t.task_description,
        "order": t.order.order_code if t.order else "",
        # Two useful fields the existing export was
        # missing, both already derivable from relationships DailyTask
        # already has (never duplicated onto the model itself).
        "category": t.task_category or "",
        "product": (t.order_item.product_name or t.order_item.description) if t.order_item else "",
        "due_date": t.due_date.strftime("%d-%m-%Y") if t.due_date else "",
        "priority": t.priority or "",
        "status": t.status, "completion_percent": t.completion_percent,
        "delay_reason": t.delay_reason or "", "remarks": t.remarks or "",
    } for t in tasks]

    jobs = job_query.order_by(ProductionJob.date.desc()).all()
    job_rows = [{
        "job_id": p.business_id or "", "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "employee": p.employee.name if p.employee else "", "order": p.order.order_code if p.order else "",
        "operation": p.operation or "", "planned_qty": p.planned_qty, "completed_qty": p.completed_qty,
        "status": p.status,
    } for p in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([
        {"sheet_name": "Tasks", "title": "STAFF TASKS",
         "columns": ["task_id", "date", "employee", "task", "order", "category", "product", "due_date",
                     "priority", "status", "completion_percent", "delay_reason", "remarks"],
         "headers": ["Task ID", "Date", "Employee", "Task", "Order", "Category", "Product", "Due Date",
                     "Priority", "Status", "Completion %", "Delay Reason", "Remarks"],
         "rows": task_rows, "subtitle": subtitle},
        {"sheet_name": "Production", "title": "PRODUCTION JOBS",
         "columns": ["job_id", "date", "employee", "order", "operation", "planned_qty", "completed_qty", "status"],
         "headers": ["Job ID", "Date", "Operator", "Order", "Operation", "Planned Qty", "Completed Qty", "Status"],
         "rows": job_rows, "subtitle": subtitle},
    ])
    filename = f"tasks_production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/project-expenses.xlsx")
def export_project_expenses(
    order_id: Optional[int] = Query(None), category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Expense Register export. Master-only, matching
    project_expenses.py's own require_role("master") gate - every field
    on ProjectExpense is financial, so there is no partial/redacted view."""
    query = db.query(ProjectExpense).options(selectinload(ProjectExpense.order))
    filters_applied = []
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if category:
        query = query.filter(ProjectExpense.category == category)
        filters_applied.append(f"Category: {category}")
    if start_date:
        query = query.filter(ProjectExpense.date >= datetime.fromisoformat(start_date))
        filters_applied.append(f"From {start_date}")
    if end_date:
        query = query.filter(ProjectExpense.date <= datetime.fromisoformat(end_date))
        filters_applied.append(f"To {end_date}")

    expenses = query.order_by(ProjectExpense.date.desc()).all()
    rows = [{
        "expense_id": e.business_id or "", "expense_code": e.expense_code,
        "date": e.date.strftime("%d-%m-%Y") if e.date else "",
        "order": e.order.order_code if e.order else "", "category": e.category,
        "description": e.description or "", "paid_to": e.paid_to or "",
        "amount": float(e.amount or 0), "approved_by": e.approved_by or "",
    } for e in expenses]
    columns = ["expense_id", "expense_code", "date", "order", "category", "description",
               "paid_to", "amount", "approved_by"]
    headers = ["Expense ID", "Expense Code", "Date", "Order", "Category", "Description",
               "Paid To", "Amount", "Approved By"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    by_category = {}
    for e in expenses:
        by_category[e.category or "Uncategorized"] = by_category.get(e.category or "Uncategorized", 0) + float(e.amount or 0)
    summary = [("Total Expenses", str(len(expenses))), ("Total Amount", f"Rs {sum(float(e.amount or 0) for e in expenses):,.2f}")]
    summary += [(f"  {cat}", f"Rs {amt:,.2f}") for cat, amt in sorted(by_category.items())]

    buffer = build_workbook([{
        "sheet_name": "Expenses", "title": "PROJECT EXPENSE REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["amount"], "subtitle": subtitle, "summary": summary,
    }])
    filename = f"expense_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/automation-log.xlsx")
def export_automation_log(rule_key: Optional[str] = None, status: Optional[str] = None,
                           db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The automation audit trail as a downloadable report.
    Reuses this module's existing Excel infrastructure (build_workbook /
    write_sheet) rather than a separate export mechanism - same
    formatting, same formula-injection sanitization, as every other
    report here. Master-only, same as GET /api/automation/logs and
    /api/audit-logs."""
    query = db.query(AutomationLog)
    if rule_key:
        query = query.filter(AutomationLog.rule_key == rule_key)
    if status:
        query = query.filter(AutomationLog.status == status)
    logs = query.order_by(AutomationLog.created_at.desc()).limit(2000).all()
    rows = [{
        "created_at": log.created_at.strftime("%d-%m-%Y %H:%M") if log.created_at else "",
        "rule_key": log.rule_key, "trigger_event": log.trigger_event, "status": log.status,
        "action_taken": log.action_taken, "condition_summary": log.condition_summary,
        "related_entity_type": log.related_entity_type or "", "related_entity_id": log.related_entity_id or "",
        "error_message": log.error_message or "",
    } for log in logs]
    columns = ["created_at", "rule_key", "trigger_event", "status", "action_taken",
               "condition_summary", "related_entity_type", "related_entity_id", "error_message"]
    headers = ["When", "Rule", "Trigger", "Status", "Action Taken",
               "Condition", "Entity Type", "Entity ID", "Error"]
    buffer = build_workbook([{"sheet_name": "Automation Log", "title": "AUTOMATION AUDIT TRAIL",
                               "columns": columns, "headers": headers, "rows": rows}])
    return xlsx_response(buffer, f"automation-log_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")


def _record_report_generated(db: Session, report_type: str, report_date, storage_identity: str = None) -> None:
    """Records this generation event and
    expires any report_history rows older than 15 days. Never touches
    any other table - the underlying business records (tasks, orders,
    etc) this report reads from are completely untouched by this
    retention sweep."""
    from app.modules.reporting.services import ReportHistory
    from datetime import timedelta
    db.query(ReportHistory).filter(
        ReportHistory.created_at < datetime.utcnow() - timedelta(days=15)
    ).delete(synchronize_session=False)
    db.add(ReportHistory(
        report_type=report_type, report_date=datetime(report_date.year, report_date.month, report_date.day),
        generated_at=datetime.utcnow(), storage_identity=storage_identity,
    ))
    db.commit()


def _daily_status_rows(db: Session, target_date):
    """The single, authoritative query behind both the Excel export and
    the email endpoint below - Employee Name / Assigned Task / Task
    Status / Pending Items from Task / Required Things, exactly as
    given in the product spec. Pending Items maps to delay_reason,
    Required Things maps to remarks - the same fields already visible
    on the task itself, not two new columns invented for this report."""
    from app.modules.operations.models import DailyTask
    from app.modules.hr.models import Employee
    tasks = (
        db.query(DailyTask).join(Employee, DailyTask.employee_id == Employee.id)
        .filter(func.date(DailyTask.date) == target_date)
        .order_by(Employee.name, DailyTask.id).all()
    )
    rows = [{
        "employee_name": t.employee.name if t.employee else "Unassigned",
        "assigned_task": t.task_description,
        "task_status": t.status,
        "pending_items": t.delay_reason or "",
        "required_things": t.remarks or "",
    } for t in tasks]
    return tasks, rows


@reports_router.get("/daily-status-report.xlsx")
def export_daily_status_report(report_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The end-of-day status report Master Users
    receive, with the exact column spec the product doc gives:
    Employee Name / Assigned Task / Task Status / Pending Items from
    Task / Required Things. Pending Items maps to delay_reason (the
    existing field DailyTask already uses for exactly this - "why
    isn't this done"), Required Things maps to remarks (the existing
    general-notes field) - not two new columns invented for this
    report, the same fields already visible on the task itself.

    Accepts an explicit date so a historical lookup
    ("last week mein kiska kya kaam reh gaya tha") can reuse this
    same endpoint/format rather than a second report implementation -
    the report and its Excel export must use the same authoritative
    information, so there is only one query here, not one for chat and
    a different one for Excel."""
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="report_date must be in YYYY-MM-DD format.")
    else:
        target_date = datetime.utcnow().date()

    tasks, rows = _daily_status_rows(db, target_date)
    _record_report_generated(db, "daily_status_report", target_date, storage_identity="download")
    columns = ["employee_name", "assigned_task", "task_status", "pending_items", "required_things"]
    headers = ["Employee Name", "Assigned Task", "Task Status", "Pending Items from Task", "Required Things"]
    buffer = build_workbook([{
        "sheet_name": "Daily Status Report", "title": f"WOODFUL DAILY STATUS REPORT - {target_date.strftime('%d %b %Y')}",
        "columns": columns, "headers": headers, "rows": rows,
        "summary": [("Total Tasks", str(len(tasks))), ("Date", target_date.strftime("%d %b %Y"))],
    }])
    return xlsx_response(buffer, f"woodful-daily-status_{target_date.strftime('%Y%m%d')}.xlsx")


@reports_router.post("/daily-status-report/send")
def send_daily_status_report_email(request: Request,
                                    report_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Automatic end-of-day delivery - emails
    the same authoritative report export_daily_status_report builds
    (via the shared _daily_status_rows query above, not a second
    implementation) to every active Master User. This app has no
    in-process scheduler, so "automatic" delivery means this endpoint
    is meant to be triggered by an external daily cron/scheduled task
    hitting it once at end of day - the same lightweight approach
    already established for send_team_summary_email, not a new
    in-process scheduling engine."""
    from app.modules.auth.auth import User
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="report_date must be in YYYY-MM-DD format.")
    else:
        target_date = datetime.utcnow().date()

    master_emails = [
        u.email for u in db.query(User).filter(User.role == "master", User.is_active == True).all()  # noqa: E712
        if u.email
    ]
    if not master_emails:
        raise HTTPException(status_code=400, detail="No active master account has an email on file.")

    tasks, rows = _daily_status_rows(db, target_date)
    if not tasks:
        raise HTTPException(status_code=404, detail=f"No tasks are recorded for {target_date.strftime('%d %b %Y')}.")
    _record_report_generated(db, "daily_status_report", target_date, storage_identity=f"email:{','.join(master_emails)}")

    lines = [f"Woodful Daily Status Report - {target_date.strftime('%d %b %Y')}", ""]
    for r in rows:
        lines.append(f"{r['employee_name']} - {r['assigned_task']} (Status: {r['task_status']})")
        if r["pending_items"]:
            lines.append(f"  Pending: {r['pending_items']}")
        if r["required_things"]:
            lines.append(f"  Required: {r['required_things']}")
    body = "\n".join(lines)
    subject = f"Woodful Daily Status Report - {target_date.strftime('%d %b %Y')}"

    from app.modules.communications.services import EmailService
    email_service = EmailService()
    results = {email: email_service.send_email(to_email=email, subject=subject, body=body, is_html=False)
               for email in master_emails}
    sent_count = sum(1 for ok in results.values() if ok)

    from app.platform.audit import log_action
    log_action(db, request, user_id=auth.get("user_id"), action="send_daily_status_report_email",
               module_name="reports",
               new_value={"recipients": master_emails, "sent_count": sent_count, "task_count": len(tasks)})

    if sent_count == 0:
        raise HTTPException(
            status_code=502,
            detail="The daily status report could not be sent right now (email service unavailable or misconfigured).",
        )
    failed = [email for email, ok in results.items() if not ok]
    message = f"Daily status report ({len(tasks)} task(s)) emailed to {sent_count} of {len(master_emails)} master account(s)."
    if failed:
        message += f" Failed for: {', '.join(failed)}."
    return {"sent": True, "message": message, "task_count": len(tasks), "sent_count": sent_count, "failed_recipients": failed}
