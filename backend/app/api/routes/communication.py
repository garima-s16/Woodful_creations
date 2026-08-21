from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.models.client import Client
from app.models.client_activity import ClientActivity
from app.models.order import Order
from app.models.order_comment import OrderComment
from app.models.daily_task import DailyTask
from app.models.task_comment import TaskComment
from app.models.notification import Notification
from app.schemas.communication import (
    SearchResult, CommunicationInsightsRequest, CommunicationInsightsResponse,
    DraftMessageRequest, DraftMessageResponse,
)
from app.services.notification_service import NotificationService
from app.services.communication_ai_service import CommunicationEntry, summarize_and_extract, draft_message

router = APIRouter(prefix="/api/communication", tags=["communication"])

RESULTS_PER_SOURCE = 8
# purpose values whose content is inherently financial (references a
# balance/payment), same sensitivity tier as PAYMENT_OVERDUE elsewhere -
# gated master-only rather than left open like follow_up/status_update.
_FINANCIAL_DRAFT_PURPOSES = {"payment_reminder"}


@router.get("/search", response_model=List[SearchResult], dependencies=[
    Depends(rate_limit("communication-search", settings.RATE_LIMIT_COMMUNICATION_SEARCH_PER_MINUTE))
])
def search_communication(q: str = Query(..., min_length=1), db: Session = Depends(get_db),
                          auth=Depends(get_current_user)):
    """Searches actual communication content - task comments, order
    (project) comments, client activity history, and notifications -
    unlike /api/search (search.py), which only matches master-record
    names/codes, never free-text content.

    Authorization: task/order comments and client activities are
    visible to every authenticated role in this app already (see
    daily_tasks.py, orders.py, client_activities.py - none of them
    gate reads by role), so this search doesn't newly restrict them
    either; matching that is deliberate, not an oversight. Notification
    content, though, IS role-gated (financial types are master-only -
    see NotificationService.FINANCIAL_NOTIFICATION_TYPES), and this
    search reuses NotificationService.visible_to unchanged, so a
    non-master search for "payment" can surface a task/order comment
    that happens to mention the word, but never the master-only
    PAYMENT_OVERDUE notification content - the exact case Family 11's
    brief calls out."""
    like = f"%{q.strip()}%"
    role = auth.get("role", "user")
    results: List[SearchResult] = []

    for tc in db.query(TaskComment).filter(TaskComment.text.ilike(like)).order_by(
        TaskComment.date.desc()).limit(RESULTS_PER_SOURCE).all():
        results.append(SearchResult(
            type="task_comment", id=tc.id, label=f"Comment on task #{tc.task_id}",
            snippet=tc.text[:200], path=f"/daily-tasks/{tc.task_id}", date=tc.date,
        ))

    for oc in db.query(OrderComment).filter(OrderComment.text.ilike(like)).order_by(
        OrderComment.date.desc()).limit(RESULTS_PER_SOURCE).all():
        order = oc.order
        results.append(SearchResult(
            type="order_comment", id=oc.id,
            label=f"Comment on {order.order_code if order else 'project'}",
            snippet=oc.text[:200], path=f"/orders/{oc.order_id}", date=oc.date,
        ))

    for ca in db.query(ClientActivity).filter(ClientActivity.summary.ilike(like)).order_by(
        ClientActivity.date.desc()).limit(RESULTS_PER_SOURCE).all():
        client = ca.client
        results.append(SearchResult(
            type="client_activity", id=ca.id,
            label=f"{ca.activity_type} with {client.name if client else 'client'}",
            snippet=ca.summary[:200], path=f"/clients/{ca.client_id}", date=ca.date,
        ))

    notif_query = NotificationService.visible_to(
        db.query(Notification).filter(
            Notification.title.ilike(like) | Notification.message.ilike(like)
        ),
        auth.get("user_id"), role,
    )
    for n in notif_query.order_by(Notification.created_at.desc()).limit(RESULTS_PER_SOURCE).all():
        results.append(SearchResult(
            type="notification", id=n.id, label=n.title, snippet=n.message[:200],
            path=n.action_path or "/", date=n.created_at,
        ))

    results.sort(key=lambda r: r.date or 0, reverse=True)
    return results


def _entries_for_order(db: Session, order_id: int) -> List[CommunicationEntry]:
    entries = [
        CommunicationEntry(author=c.author, text=c.text, date=c.date, source_type="order_comment")
        for c in db.query(OrderComment).filter(OrderComment.order_id == order_id).all()
    ]
    task_ids = [t.id for t in db.query(DailyTask.id).filter(DailyTask.order_id == order_id).all()]
    if task_ids:
        entries += [
            CommunicationEntry(author=c.author, text=c.text, date=c.date, source_type="task_comment")
            for c in db.query(TaskComment).filter(TaskComment.task_id.in_(task_ids)).all()
        ]
    return entries


def _entries_for_client(db: Session, client_id: int) -> List[CommunicationEntry]:
    return [
        CommunicationEntry(author=a.logged_by or "Unknown", text=a.summary, date=a.date, source_type="client_activity")
        for a in db.query(ClientActivity).filter(ClientActivity.client_id == client_id).all()
    ]


def _resolve_entries(db: Session, entity_type: str, entity_id: int) -> List[CommunicationEntry]:
    if entity_type == "order":
        if not db.query(Order).filter(Order.id == entity_id).first():
            raise HTTPException(status_code=404, detail="Order not found")
        return _entries_for_order(db, entity_id)
    if entity_type == "client":
        if not db.query(Client).filter(Client.id == entity_id).first():
            raise HTTPException(status_code=404, detail="Client not found")
        return _entries_for_client(db, entity_id)
    raise HTTPException(status_code=400, detail="entity_type must be 'order' or 'client'")


@router.post("/insights", response_model=CommunicationInsightsResponse, dependencies=[
    Depends(rate_limit("communication-ai", settings.RATE_LIMIT_COMMUNICATION_AI_PER_MINUTE))
])
def get_communication_insights(data: CommunicationInsightsRequest, db: Session = Depends(get_db),
                                auth=Depends(get_current_user)):
    """Rule-based extractive summary/action-items/unanswered-items over
    an order's or client's actual recorded communication - see
    communication_ai_service.py's module docstring for why this is
    explicitly NOT presented as genuine AI reasoning (this app has no
    real LLM integration)."""
    entries = _resolve_entries(db, data.entity_type, data.entity_id)
    insights = summarize_and_extract(entries)
    return CommunicationInsightsResponse(
        method=insights.method, summary=insights.summary, action_items=insights.action_items,
        unanswered_items=insights.unanswered_items, entry_count=insights.entry_count,
    )


@router.post("/draft", response_model=DraftMessageResponse, dependencies=[
    Depends(rate_limit("communication-ai", settings.RATE_LIMIT_COMMUNICATION_AI_PER_MINUTE))
])
def get_draft_message(data: DraftMessageRequest, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    """Returns a template-filled draft for the user to review and send
    themselves - this app has no outbound email/SMS integration, so
    there is nothing here that could send it even if asked to; Family
    11 requires explicit human authorization for any external
    communication, and the absence of a send path enforces that by
    construction, not just by policy."""
    if data.purpose in _FINANCIAL_DRAFT_PURPOSES and auth.get("role", "user") not in ("master",):
        raise HTTPException(status_code=403, detail="This draft type requires a master account.")

    if data.entity_type == "order":
        order = db.query(Order).filter(Order.id == data.entity_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        name = order.client.name if order.client else "there"
        subject = order.order_code
    elif data.entity_type == "client":
        client = db.query(Client).filter(Client.id == data.entity_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        name = client.name
        subject = client.name
    else:
        raise HTTPException(status_code=400, detail="entity_type must be 'order' or 'client'")

    try:
        draft = draft_message(data.purpose, name=name, subject=subject, sender=auth.get("email") or "Woodful Creations",
                               detail=data.detail)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown draft purpose.")

    return DraftMessageResponse(
        method="template", draft=draft,
        note="This is a draft only - review and send it yourself through your usual channel. Nothing is sent automatically.",
    )
