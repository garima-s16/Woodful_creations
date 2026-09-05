from typing import List, Optional
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import DailyTask, TaskComment
from app.modules.sales.models import Order, OrderItem
from app.modules.auth.models import User
from app.modules.hr.models import Employee
from app.modules.communications.services.notification_service import NotificationService
from app.modules.communications.services.mention_service import notify_mentions
from app.modules.operations.schemas import (
    DailyTaskCreate, DailyTaskUpdate, DailyTaskResponse, CompleteAndAssignNext,
    TaskCommentCreate, TaskCommentResponse,
)
from app.platform.database.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/daily-tasks", tags=["daily-tasks"])


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


def _serialize_task(db: Session, task: DailyTask) -> DailyTaskResponse:
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
    return response


def _serialize_tasks(db: Session, tasks) -> List[DailyTaskResponse]:
    return [_serialize_task(db, t) for t in tasks]


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


@router.get("/", response_model=List[DailyTaskResponse])
def list_daily_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                      order_item_id: Optional[int] = Query(None),
                      date: Optional[datetime] = Query(None), status: Optional[str] = Query(None),
                      exclude_status: Optional[str] = Query(None),
                      task_category: Optional[str] = Query(None), priority: Optional[str] = Query(None),
                      due_date_from: Optional[datetime] = Query(None), due_date_to: Optional[datetime] = Query(None),
                      overdue: bool = Query(False),
                      mine: bool = Query(False),
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
    return _serialize_tasks(db, tasks)


@router.post("/", response_model=DailyTaskResponse, status_code=201)
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
                    from app.modules.communications.services.email_service import EmailService
                    EmailService().send_email(to_email=employee.email, subject=email_subject, body=email_body, is_html=False)
                except Exception as e:
                    logging.getLogger(__name__).error(f"Task assignment email failed for {employee.email}: {e}")
        return _serialize_task(db, task)
    raise HTTPException(status_code=500, detail="Unable to generate a unique task code, please try again")


@router.get("/{task_id}", response_model=DailyTaskResponse)
def get_daily_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    task = db.query(DailyTask).options(
        joinedload(DailyTask.employee),
        joinedload(DailyTask.order).joinedload(Order.client),
        joinedload(DailyTask.order_item),
    ).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_task(db, task)


@router.post("/{task_id}/send-email")
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
    from app.modules.communications.services.email_service import EmailService
    sent = EmailService().send_email(to_email=task.employee.email, subject=subject, body=body, is_html=False)

    from app.platform.audit.audit import log_action
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


@router.post("/send-team-summary-email")
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

    from app.modules.communications.services.email_service import EmailService
    email_service = EmailService()
    results = {email: email_service.send_email(to_email=email, subject=subject, body=body, is_html=False)
               for email in master_emails}
    sent_count = sum(1 for ok in results.values() if ok)

    from app.platform.audit.audit import log_action
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


# A normal user may update ONLY their own assigned
# task, and only these fields on it. Every other field (assignment,
# order/product context, description, priority, dates, ...) is a
# management operation reserved for Master.
EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "completion_percent", "delay_reason", "remarks"}


@router.put("/{task_id}", response_model=DailyTaskResponse)
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
                from app.modules.communications.services.email_service import EmailService
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


@router.post("/{task_id}/complete-and-assign-next", response_model=DailyTaskResponse, status_code=201)
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
                from app.modules.communications.services.email_service import EmailService
                EmailService().send_email(to_email=next_employee.email, subject=email_subject, body=email_body, is_html=False)
            except Exception as e:
                logging.getLogger(__name__).error(f"Handoff task assignment email failed for {next_employee.email}: {e}")
        return next_task_response
    raise HTTPException(status_code=500, detail="Unable to generate a unique task code, please try again")


@router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
def list_task_comments(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(DailyTask).filter(DailyTask.id == task_id).first():
        raise HTTPException(status_code=404, detail="Task not found")
    return db.query(TaskComment).filter(TaskComment.task_id == task_id).order_by(TaskComment.date.asc()).all()


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
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
