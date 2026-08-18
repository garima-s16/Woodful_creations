from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# Notification types whose content is inherently financial - even when
# broadcast (no specific recipient), only master should see
# these. Operational broadcasts (LOW_STOCK, OUT_OF_STOCK,
# PURCHASE_RECEIVED - quantities/materials/suppliers, never a price)
# are visible to everyone, matching "Employee CAN view stock/material
# information" from the access-control brief.
FINANCIAL_NOTIFICATION_TYPES = {"PAYMENT_OVERDUE", "PAYMENT_DUE"}


def _visible_to(query, user_id: int, role: str):
    """A notification is visible if it's addressed to this specific
    user, or it's a broadcast (no specific recipient) whose type isn't
    financial - financial broadcasts stay master-only even
    though they have no specific recipient set."""
    own = Notification.recipient_user_id == user_id
    if role in ("master",):
        return query.filter(or_(own, Notification.recipient_user_id.is_(None)))
    operational_broadcast = and_(
        Notification.recipient_user_id.is_(None), Notification.notification_type.notin_(FINANCIAL_NOTIFICATION_TYPES),
    )
    return query.filter(or_(own, operational_broadcast))


@router.get("/", response_model=List[NotificationResponse])
def list_notifications(unread_only: bool = Query(False), limit: int = Query(50, ge=1, le=200),
                        db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Runs the real on-demand checks first, so opening the panel always
    reflects current state - there's no background scheduler in this
    app, so "check when someone actually looks" is the real mechanism,
    made safe to call repeatedly by dedup_key."""
    NotificationService.run_all_checks(db)

    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), auth=Depends(get_current_user)):
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


@router.put("/read-all")
def mark_all_read(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    updated = query.filter(Notification.is_read.is_(False)).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"marked_read": updated}
