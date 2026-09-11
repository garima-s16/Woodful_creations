"""Communications domain API routes: search/insights/drafts/email-
status (communication_router), notifications (notifications_router),
and automation rules (automation_router). Combines the former
communication.py, notifications.py, and automation.py."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.platform.security import rate_limit
from app.platform.config import settings
from app.platform.audit import log_action
from app.modules.communications.services import EmailService
from app.modules.clients.models import Client, ClientActivity
from app.modules.clients.services import ClientEmailSendResult
from app.modules.sales.models import Order, OrderComment
from app.modules.operations.models import DailyTask, TaskComment
from app.modules.communications.models import Notification
from app.modules.communications.schemas import SearchResult, CommunicationInsightsRequest, CommunicationInsightsResponse, DraftMessageRequest, DraftMessageResponse
from app.modules.communications.services import NotificationService
from app.modules.communications.services import CommunicationEntry, summarize_and_extract, draft_message
from fastapi import APIRouter, Depends, HTTPException, Query
from app.platform.security import get_current_user
from app.modules.communications.schemas import NotificationResponse
from app.modules.communications.automation import AutomationService
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.platform.security import require_role
from app.modules.communications.models import AutomationLog
from app.modules.communications.schemas import AutomationLogResponse, AutomationRuleInfo, AutomationRunResult


# --- communication.py ---
communication_router = APIRouter(prefix="/api/communication", tags=["communication"])


RESULTS_PER_SOURCE = 8


_FINANCIAL_DRAFT_PURPOSES = {"payment_reminder"}


@communication_router.get("/search", response_model=List[SearchResult], dependencies=[
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
    PAYMENT_OVERDUE notification content - the exact case the
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


@communication_router.post("/insights", response_model=CommunicationInsightsResponse, dependencies=[
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


@communication_router.post("/draft", response_model=DraftMessageResponse, dependencies=[
    Depends(rate_limit("communication-ai", settings.RATE_LIMIT_COMMUNICATION_AI_PER_MINUTE))
])
def get_draft_message(data: DraftMessageRequest, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    """Returns a template-filled draft for the user to review and send
    themselves - this app has no outbound email/SMS integration, so
    there is nothing here that could send it even if asked to. Any
    external communication requires explicit human authorization, and
    the absence of a send path enforces that by construction, not
    just by policy."""
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


class EmailTestRequest(BaseModel):
    recipient_email: str


class EmailStatusResponse(BaseModel):
    is_configured: bool
    sender_email: str
    sender_name: str
    smtp_server: str
    smtp_port: int


@communication_router.get("/email-status", response_model=EmailStatusResponse, dependencies=[Depends(require_role("master"))])
def get_email_status():
    """Master-only email integration status (spec section 4) - reports
    only non-secret configuration facts. Never returns
    SENDER_PASSWORD or any credential value, matching the explicit
    "do not expose secrets even to Master Users through normal API
    responses" requirement - this exists so a Master can confirm the
    central Woodful sender identity is set up correctly without
    anyone needing shell/server access to check backend/.env."""
    return EmailStatusResponse(
        is_configured=bool(settings.SENDER_EMAIL and settings.SENDER_PASSWORD),
        sender_email=settings.SENDER_EMAIL, sender_name=settings.SENDER_NAME,
        smtp_server=settings.SMTP_SERVER, smtp_port=settings.SMTP_PORT,
    )


@communication_router.post("/email-test", response_model=ClientEmailSendResult, dependencies=[Depends(rate_limit("email-test", 3, 60))])
def send_test_email(data: EmailTestRequest, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Master-only "test email configuration" (spec section 4) - sends
    one real email through the exact same EmailService every business
    email already uses, so a successful test genuinely proves the
    configured Woodful sender identity can deliver mail, not a
    separate check that could pass while real sends still fail. The
    recipient is never sent from - the central SENDER_EMAIL is what
    the frontend can never override, tested here the same way."""
    email_service = EmailService()
    sent = email_service.send_email(
        to_email=data.recipient_email, subject="Woodful email configuration test",
        body="This is a test email confirming Woodful's email configuration is working correctly.\n\n"
             "If you received this, outgoing email is set up correctly.",
    )
    log_action(db, request, user_id=auth.get("user_id"), action="send_test_email", module_name="communication",
               new_value={"recipient": data.recipient_email, "sent": sent, "sender": email_service.sender_email})
    if not sent:
        reason_text = {
            "missing_configuration": "Email sending is not configured on this server (SENDER_EMAIL/SENDER_PASSWORD/SMTP settings).",
            "authentication_failed": "The email account's login was rejected by the mail server - check the sender email and app password.",
            "connection_failed": "Could not reach the mail server - check SMTP_SERVER/SMTP_PORT and network/firewall settings.",
            "smtp_error": "The mail server rejected this message.",
            "unknown_error": "An unexpected error occurred while sending.",
        }.get(email_service.last_error, "email service unavailable or misconfigured")
        raise HTTPException(status_code=502, detail=f"Test email could not be sent ({reason_text}).")
    return ClientEmailSendResult(sent=True, message=f"Test email sent to {data.recipient_email}.")


# --- notifications.py ---
notifications_router = APIRouter(prefix="/api/notifications", tags=["notifications"])


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


@notifications_router.get("/", response_model=List[NotificationResponse])
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


@notifications_router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The most frequently-polled notification endpoint (typically a
    badge count on a short client-side timer) - must never independently
    re-run the full automation engine while the scheduler is active."""
    _run_on_demand_checks_if_scheduler_disabled(db)
    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    count = query.filter(Notification.is_read.is_(False)).count()
    return {"count": count}


@notifications_router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(notification_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    # Defect repair: this used to only check
    # `recipient_user_id in (None, my_id)`, which treats EVERY
    # broadcast (recipient_user_id is None) as visible to any
    # authenticated user - including a master-only financial broadcast
    # (see FINANCIAL_NOTIFICATION_TYPES/visible_to in services.py,
    # already the single authoritative rule for the list endpoint and
    # communication search, but never applied here). That let any
    # non-master user mark one read AND receive its title/message
    # (financial content) back in the response body. Now goes through
    # the same visible_to() rule everywhere else in this router does.
    visible = NotificationService.visible_to(
        db.query(Notification).filter(Notification.id == notification_id),
        auth.get("user_id"), auth.get("role", "user"),
    ).first()
    if not visible:
        raise HTTPException(status_code=403, detail="This notification isn't addressed to you.")
    notification.is_read = True
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@notifications_router.put("/read-all", dependencies=[
    Depends(rate_limit("notifications-mark-all-read", settings.RATE_LIMIT_BULK_NOTIFICATION_PER_MINUTE))
])
def mark_all_read(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = _visible_to(db.query(Notification), auth.get("user_id"), auth.get("role", "user"))
    updated = query.filter(Notification.is_read.is_(False)).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"marked_read": updated}


# --- automation.py ---
automation_router = APIRouter(prefix="/api/automation", tags=["automation"])


@automation_router.get("/rules", response_model=List[AutomationRuleInfo])
def list_rules(auth=Depends(require_role("master"))):
    """The EVENT -> ACTION registry itself - static, not a DB query, so
    the frontend can show what automation exists without needing a log
    entry to have fired yet."""
    return AutomationService.RULES


@automation_router.get("/logs", response_model=List[AutomationLogResponse])
def list_logs(rule_key: Optional[str] = Query(None), status: Optional[str] = Query(None),
              related_entity_type: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500),
              db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Master-only, same as audit-logs - this is an internal operations
    trail, not a user-facing feed (that's Notification, already visible
    per its own RBAC in notifications.py)."""
    query = db.query(AutomationLog)
    if rule_key:
        query = query.filter(AutomationLog.rule_key == rule_key)
    if status:
        query = query.filter(AutomationLog.status == status)
    if related_entity_type:
        query = query.filter(AutomationLog.related_entity_type == related_entity_type)
    return query.order_by(AutomationLog.created_at.desc()).limit(limit).all()


@automation_router.post("/run", response_model=AutomationRunResult)
def run_automation(source: str = Query("scheduled_job", pattern="^(scheduled_job|manual_trigger)$"),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Evaluates every rule right now. This app has no in-process
    background scheduler (see AutomationService's module docstring), so
    this is the endpoint a real external scheduler (cron, a hosting
    platform's scheduled task) should call periodically - source defaults
    to "scheduled_job" for that case; the frontend can pass
    source=manual_trigger for an explicit "Run now" button. Idempotent:
    calling this twice in a row with nothing new in between logs 0 the
    second time."""
    before_count = db.query(AutomationLog).count()
    AutomationService.run_all(db, trigger_event=source)
    after_count = db.query(AutomationLog).count()
    return AutomationRunResult(trigger_event=source, logged=after_count - before_count)
