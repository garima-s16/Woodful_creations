from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.communications.models import Notification
from app.modules.communications.schemas import NotificationResponse
from app.modules.communications.services.notification_service import NotificationService
from app.modules.communications.services.automation_service import AutomationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _visible_to(query, user_id: int, role: str):
    """Thin alias kept for readability at call sites in this file - the
    actual rule (and FINANCIAL_NOTIFICATION_TYPES) now live in
    NotificationService (see there for why), shared with the
    communication search so both use exactly one definition of "who can
    see this notification"."""
    return NotificationService.visible_to(query, user_id, role)


def _run_on_demand_checks_if_scheduler_disabled(db: Session) -> None:
    """The on-demand fallback path (Family P0 production-readiness
    review, section 16): when the background automation scheduler
    (app/main.py's _automation_scheduler_loop) is enabled, it already
    keeps notifications fresh on its own interval - these read
    endpoints must not ALSO re-run the entire automation engine on
    every single call, which would mean every notification-panel open
    and every unread-count poll, across every logged-in user,
    independently re-executes all automation rules on top of what the
    scheduler is already doing. Only when the scheduler is disabled do
    these endpoints fall back to running the checks themselves, so
    notifications still stay current in that configuration."""
    if settings.AUTOMATION_SCHEDULER_ENABLED:
        return
    AutomationService.run_all(db, trigger_event="on_demand_check")
    NotificationService.run_all_checks(db)


@router.get("/", response_model=List[NotificationResponse])
def list_notifications(unread_only: bool = Query(False), limit: int = Query(50, ge=1, le=200),
                        db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Reads notification state. Only runs the on-demand automation
    fallback itself when the background scheduler is disabled (see
    _run_on_demand_checks_if_scheduler_disabled) - with the scheduler
    enabled (the default), this is a pure read, exactly as its name
    says, and does not re-run the automation engine on every poll."""
    _run_on_demand_checks_if_scheduler_disabled(db)

    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The most frequently-polled notification endpoint (typically a
    badge count on a short client-side timer) - must never independently
    re-run the full automation engine while the scheduler is active."""
    _run_on_demand_checks_if_scheduler_disabled(db)
    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    count = query.filter(Notification.is_read.is_(False)).count()
    return {"count": count}


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(notification_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    # A user can only mark their own or a broadcast notification read -
    # not someone else's specifically-addressed one.
    if notification.recipient_user_id not in (None, auth.get("user_id")):
        raise HTTPException(status_code=403, detail="This notification isn't addressed to you.")
    notification.is_read = True
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.put("/read-all", dependencies=[
    Depends(rate_limit("notifications-mark-all-read", settings.RATE_LIMIT_BULK_NOTIFICATION_PER_MINUTE))
])
def mark_all_read(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    updated = query.filter(Notification.is_read.is_(False)).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"marked_read": updated}
