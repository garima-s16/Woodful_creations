from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.daily_task import DailyTask
from app.models.task_comment import TaskComment
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.mention_service import notify_mentions
from app.schemas.daily_task import (
    DailyTaskCreate, DailyTaskUpdate, DailyTaskResponse, CompleteAndAssignNext,
    TaskCommentCreate, TaskCommentResponse,
)
from app.utils.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/daily-tasks", tags=["daily-tasks"])


@router.get("/", response_model=List[DailyTaskResponse])
def list_daily_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                      date: Optional[datetime] = Query(None), status: Optional[str] = Query(None),
                      mine: bool = Query(False), db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(DailyTask)
    if mine:
        my_employee_id = auth.get("employee_id")
        if my_employee_id is None:
            raise HTTPException(status_code=400, detail="Your account is not linked to an employee record.")
        query = query.filter(DailyTask.employee_id == my_employee_id)
    elif employee_id:
        query = query.filter(DailyTask.employee_id == employee_id)
    if order_id:
        query = query.filter(DailyTask.order_id == order_id)
    if date:
        query = query.filter(DailyTask.date == date)
    if status:
        query = query.filter(DailyTask.status == status)
    return query.order_by(DailyTask.date.desc()).all()


@router.post("/", response_model=DailyTaskResponse, status_code=201)
def create_daily_task(data: DailyTaskCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    payload = data.dict(exclude={"task_code"})
    if not payload.get("created_by"):
        payload["created_by"] = auth.get("email")
    for _ in range(5):
        code = generate_unique_code(db, DailyTask, "task_code", "TSK-")
        task = DailyTask(**payload, task_code=code, business_id=generate_business_id(db))
        db.add(task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(task)
        if task.employee_id:
            recipient = db.query(User).filter(User.employee_id == task.employee_id).first()
            if recipient:
                NotificationService.notify(
                    db, notification_type="TASK_ASSIGNED", severity="INFO",
                    title="New task assigned", message=f"{task.task_description}",
                    recipient_user_id=recipient.id, related_entity_type="task",
                    related_entity_id=task.id, action_path=f"/daily-tasks/{task.id}",
                )
        return task
    raise HTTPException(status_code=500, detail="Unable to generate a unique task code, please try again")


@router.get("/{task_id}", response_model=DailyTaskResponse)
def get_daily_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "delay_reason"}


@router.put("/{task_id}", response_model=DailyTaskResponse)
def update_daily_task(task_id: int, data: DailyTaskUpdate, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    role = auth.get("role", "user")
    update_data = data.dict(exclude_unset=True)

    if role not in ("master",):
        # Any employee can change any task's status - not restricted to
        # tasks assigned to them (tasks are visible to everyone, and
        # status is the one field every employee may touch regardless
        # of assignment). All other fields remain master-only.
        disallowed = set(update_data.keys()) - EMPLOYEE_SELF_SERVICE_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"You can only update: {', '.join(sorted(EMPLOYEE_SELF_SERVICE_FIELDS))}. "
                       f"Not allowed to change: {', '.join(sorted(disallowed))}.",
            )

    if update_data.get("status") == "DONE":
        update_data["completion_percent"] = 100
        if task.status != "DONE":
            update_data["actual_completed_at"] = datetime.utcnow()

    status_changed = "status" in update_data and update_data["status"] != task.status

    for field, value in update_data.items():
        setattr(task, field, value)
    db.add(task)
    db.commit()
    db.refresh(task)

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
    return task


@router.post("/{task_id}/complete-and-assign-next", response_model=DailyTaskResponse, status_code=201)
def complete_and_assign_next(task_id: int, data: CompleteAndAssignNext, db: Session = Depends(get_db),
                              auth=Depends(get_current_user)):
    """Completes the current task and creates a new, linked task for
    the next person - the original is never overwritten, so the full
    handoff chain (previous_task_id) stays intact."""
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    role = auth.get("role", "user")
    if role not in ("master",) and task.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only complete and hand off your own tasks.")

    task.status = "DONE"
    task.completion_percent = 100
    db.add(task)

    payload = {
        "date": data.next_due_date, "employee_id": data.next_employee_id, "order_id": task.order_id,
        "task_description": data.next_task_description, "priority": data.next_priority,
        "created_by": auth.get("email"), "previous_task_id": task.id, "remarks": data.note,
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
        recipient = db.query(User).filter(User.employee_id == data.next_employee_id).first()
        if recipient:
            NotificationService.notify(
                db, notification_type="TASK_ASSIGNED", severity="INFO",
                title="Next action assigned", message=data.next_task_description,
                recipient_user_id=recipient.id, related_entity_type="task",
                related_entity_id=next_task.id, action_path=f"/daily-tasks/{next_task.id}",
            )
        return next_task
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
    # Family 11 - @mentions in a task comment notify the mentioned user
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
