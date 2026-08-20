from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService, FINANCIAL_NOTIFICATION_TYPES
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _visible_to(query, user_id: int, role: str):
    """Thin alias kept for readability at call sites in this file - the
    actual rule (and FINANCIAL_NOTIFICATION_TYPES) now live in
    NotificationService (see there for why), shared with Family 11's
    communication search so both use exactly one definition of "who can
    see this notification"."""
    return NotificationService.visible_to(query, user_id, role)


@router.get("/", response_model=List[NotificationResponse])
def list_notifications(unread_only: bool = Query(False), limit: int = Query(50, ge=1, le=200),
                        db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Runs the real on-demand checks first, so opening the panel always
    reflects current state - there's no background scheduler in this
    app, so "check when someone actually looks" is the real mechanism,
    made safe to call repeatedly by dedup_key. Also runs Family 13's
    automation rules (task overdue, low-stock reorder recommendation,
    purchase delivery approaching, project delayed, production blocked -
    payment overdue was already covered by NotificationService above).
    Runs before NotificationService.run_all_checks below - its payment
    -overdue rule diffs the notification set right before/after calling
    the exact same NotificationService check, so it needs to run first
    to see that notification as newly created; run_all_checks below then
    calling the same payment check again is a harmless dedup no-op, and
    still needed here for check_stock_notifications (LOW_STOCK/
    OUT_OF_STOCK), which stays exactly as it already was."""
    AutomationService.run_all(db, trigger_event="on_demand_check")
    NotificationService.run_all_checks(db)

    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    AutomationService.run_all(db, trigger_event="on_demand_check")
    NotificationService.run_all_checks(db)
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
