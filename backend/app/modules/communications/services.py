"""Communications services: outbound email (EmailService),
in-app notifications (NotificationService), @mention extraction/
notification, and AI-assisted communication summarization/drafting.
Combines the former email_service.py, notification_service.py,
mention_service.py, and communication_ai_service.py. automation_service.py
remains separate (see automation.py) given its size and distinct
responsibility."""
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional
import logging
from app.platform.config import settings
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from app.modules.communications.models import Notification
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.sales.models import Order
from app.modules.auth.auth import User
from app.platform.ids import generate_business_id
import re
from typing import List
from dataclasses import dataclass, field
from typing import List, Optional


# --- email_service.py ---
logger = logging.getLogger(__name__)


_SMTP_TIMEOUT_SECONDS = 15


class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.sender_email = settings.SENDER_EMAIL
        self.sender_password = settings.SENDER_PASSWORD
        self.sender_name = settings.SENDER_NAME
        # The real reason the last send_email call failed, in a form
        # safe to show a user (never the password/credential value
        # itself) - callers that only check the returned bool are
        # completely unaffected; callers that want to surface a
        # specific reason (see orders.py/estimates.py/payments.py's
        # invoice-send endpoints) can read this after a False result.
        self.last_error: Optional[str] = None

    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False,
                    attachment_bytes: Optional[bytes] = None, attachment_filename: Optional[str] = None) -> bool:
        self.last_error = None
        try:
            if not self.sender_email or not self.sender_password:
                self.last_error = "missing_configuration"
                logger.warning("Email send skipped: SENDER_EMAIL/SENDER_PASSWORD not configured")
                return False
            if not self.smtp_server or not self.smtp_port:
                self.last_error = "missing_configuration"
                logger.warning("Email send skipped: SMTP_SERVER/SMTP_PORT not configured")
                return False

            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html' if is_html else 'plain'))

            if attachment_bytes is not None and attachment_filename:
                part = MIMEApplication(attachment_bytes, Name=attachment_filename)
                part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
                msg.attach(part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to_email}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            # The SMTP server's own rejection reason (e.g. "Username
            # and Password not accepted") - never the credential
            # value itself, which smtplib never includes here.
            self.last_error = "authentication_failed"
            logger.error(f"Email send failed - SMTP authentication rejected: {e.smtp_code} {e.smtp_error}")
            return False
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, socket.timeout, ConnectionError, OSError) as e:
            self.last_error = "connection_failed"
            logger.error(f"Email send failed - could not reach SMTP server {self.smtp_server}:{self.smtp_port}: {e}")
            return False
        except smtplib.SMTPException as e:
            self.last_error = "smtp_error"
            logger.error(f"Email send failed - SMTP error: {e}")
            return False
        except Exception as e:
            self.last_error = "unknown_error"
            logger.error(f"Email send failed: {str(e)}")
            return False


# --- notification_service.py ---
FINANCIAL_NOTIFICATION_TYPES = {
    "PAYMENT_OVERDUE", "PAYMENT_DUE", "PURCHASE_RECOMMENDED", "ESTIMATE_PENDING_RESPONSE",
    "SALARY_ADVANCE_APPROVAL_REQUIRED", "PAYROLL_FINALIZATION_OVERDUE",
}


class NotificationService:
    """Real, event-driven notifications only - every notify() call here
    traces back to an actual condition in the database at the moment
    it's checked, never a fabricated/demo row. There is no background
    job scheduler in this app, so the check_* functions run on demand
    (wired into the notifications list endpoint) rather than on a timer -
    dedup_key is what makes that safe to call repeatedly without
    spamming duplicates."""

    @staticmethod
    def notify(db: Session, notification_type: str, severity: str, title: str, message: str,
               recipient_user_id: Optional[int] = None, related_entity_type: Optional[str] = None,
               related_entity_id: Optional[int] = None, action_path: Optional[str] = None,
               dedup_key: Optional[str] = None,
               recipient_email: Optional[str] = None, email_subject: Optional[str] = None,
               email_body: Optional[str] = None) -> Notification:
        """Creates a notification, unless an unread one with the same
        dedup_key already exists (do not create the same notification
        repeatedly on every dashboard refresh).

        If recipient_email is given, also
        emails it (subject/body default to title/message if not given
        separately - richer content like task assignment emails should
        pass its own email_subject/email_body). Extending this one
        function rather than adding a parallel email trigger. A failed
        email never blocks or rolls back the notification itself (do
        not corrupt the related record merely because email failed) -
        caught and logged, not raised.

        Defect repair (F138 P9.1): the dedup_key lookup below is a
        fast-path check only, not the actual guarantee - two concurrent
        callers (two requests, or the on-demand check racing the
        background scheduler) can both pass it before either has
        inserted, and would otherwise both create a live notification
        for the same situation. The real guarantee is the database's
        own partial unique index on (dedup_key WHERE is_read=false) -
        see Notification's docstring - enforced here via the same
        try-commit/except IntegrityError/rollback-and-fetch idiom
        hr/services.py's create_employee already uses for its own
        unique-code races: if the insert loses the race, that's not a
        real error, it just means someone else's insert already
        satisfied this exact request, so we return their row instead of
        ours."""
        if dedup_key:
            existing = db.query(Notification).filter(
                Notification.dedup_key == dedup_key, Notification.is_read.is_(False)
            ).first()
            if existing:
                return existing

        notification = Notification(
            notification_type=notification_type, severity=severity, title=title, message=message,
            recipient_user_id=recipient_user_id, related_entity_type=related_entity_type,
            related_entity_id=related_entity_id, action_path=action_path, dedup_key=dedup_key,
            business_id=generate_business_id(db),
        )
        db.add(notification)
        if dedup_key:
            try:
                db.commit()
            except IntegrityError:
                # Lost the race to another concurrent caller inserting
                # the same unread dedup_key - not a real failure, fetch
                # and return the row that won instead of raising.
                db.rollback()
                existing = db.query(Notification).filter(
                    Notification.dedup_key == dedup_key, Notification.is_read.is_(False)
                ).first()
                if existing:
                    return existing
                raise  # genuinely unexpected - some other constraint fired
        else:
            db.commit()
        db.refresh(notification)

        if recipient_email:
            try:
                EmailService().send_email(
                    to_email=recipient_email, subject=email_subject or title,
                    body=email_body or message, is_html=False,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Notification email failed for {recipient_email}: {e}")

        return notification

    @staticmethod
    def check_stock_notifications(db: Session):
        """LOW_STOCK / OUT_OF_STOCK, driven by the same Material.stock_status
        every other part of the app already uses - not a separately
        re-derived threshold check."""
        materials = db.query(Material).all()

        # Batches the "is this genuinely new" dedup lookup into one
        # query instead of one per material - the actual creation
        # (notify()) still checks its own dedup_key per call, since
        # notify() is shared, widely-used infrastructure and a
        # batch-aware rewrite of it is out of proportion to this fix.
        existing_dedup_keys = {
            row[0] for row in db.query(Notification.dedup_key).filter(
                Notification.is_read.is_(False),
                (Notification.dedup_key.like("out_of_stock:material:%"))
                | (Notification.dedup_key.like("low_stock:material:%")),
            ).all()
        }

        for m in materials:
            status = m.stock_status
            if status == "OUT OF STOCK":
                dedup_key = f"out_of_stock:material:{m.id}"
                title = f"{m.name} is out of stock"
                message = f"{m.name} ({m.material_code}) has 0 {m.unit} remaining."
                is_genuinely_new = dedup_key not in existing_dedup_keys
                NotificationService.notify(
                    db, notification_type="OUT_OF_STOCK", severity="CRITICAL",
                    title=title, message=message,
                    related_entity_type="material", related_entity_id=m.id,
                    action_path=f"/materials/{m.id}", dedup_key=dedup_key,
                )
                if is_genuinely_new:
                    NotificationService._email_all_masters(db, title, message)
            elif status == "LOW STOCK":
                dedup_key = f"low_stock:material:{m.id}"
                title = f"{m.name} is running low"
                message = (f"{m.name} ({m.material_code}) is at {m.current_stock} {m.unit}, "
                           f"at or below the reorder level of {m.minimum_stock} {m.unit}.")
                is_genuinely_new = dedup_key not in existing_dedup_keys
                NotificationService.notify(
                    db, notification_type="LOW_STOCK", severity="WARNING",
                    title=title, message=message,
                    related_entity_type="material", related_entity_id=m.id,
                    action_path=f"/materials/{m.id}", dedup_key=dedup_key,
                )
                if is_genuinely_new:
                    NotificationService._email_all_masters(db, title, message)

    @staticmethod
    def _email_all_masters(db: Session, subject: str, body: str) -> None:
        """Shared by check_stock_notifications' two alert types - emails
        every active Master User directly (bypassing notify()'s
        single-recipient email parameter, since a broadcast notification
        has no single recipient to attach an email to). A failed email
        for one master never blocks the others, matching the same
        "log, don't raise" discipline notify() itself already uses."""
        import logging
        masters = db.query(User).filter(User.role == "master", User.is_active == True).all()  # noqa: E712
        for master in masters:
            if not master.email:
                continue
            try:
                EmailService().send_email(to_email=master.email, subject=subject, body=body, is_html=False)
            except Exception as e:
                logging.getLogger(__name__).error(f"Stock alert email failed for {master.email}: {e}")

    @staticmethod
    def notify_purchase_received(db: Session, purchase: Purchase):
        """Called directly from ProcurementService.record_purchase/
        mark_purchase_received - a real event as it happens, not a
        periodic scan."""
        material_name = purchase.material.name if purchase.material else "Material"
        supplier_name = purchase.supplier.name if purchase.supplier else "Supplier"
        NotificationService.notify(
            db, notification_type="PURCHASE_RECEIVED", severity="SUCCESS",
            title=f"{material_name} received",
            message=f"{purchase.quantity} {purchase.unit} of {material_name} received from {supplier_name}.",
            related_entity_type="purchase", related_entity_id=purchase.id,
            action_path=f"/materials/{purchase.material_id}" if purchase.material_id else None,
            # No dedup_key - each purchase is a genuinely distinct event,
            # not a recurring state to collapse into one notification.
        )

    @staticmethod
    def check_payment_overdue_notifications(db: Session):
        """Reuses the exact same "overdue" rule already established for
        the Orders page's overdue_only filter (balance outstanding,
        order placed 30+ days ago) - there's no due-date field on Order,
        so this is the same stated approximation used everywhere else,
        not a separately-invented threshold."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        overdue_orders = db.query(Order).filter(Order.balance > 0, Order.order_date < cutoff).all()
        for order in overdue_orders:
            client_name = order.client.name if order.client else "Client"
            NotificationService.notify(
                db, notification_type="PAYMENT_OVERDUE", severity="CRITICAL",
                title=f"Payment overdue - {order.order_code}",
                message=f"{client_name}'s order {order.order_code} has an outstanding balance of "
                        f"Rs {float(order.balance):,.2f}, placed over 30 days ago.",
                related_entity_type="order", related_entity_id=order.id,
                action_path=f"/orders/{order.id}", dedup_key=f"payment_overdue:order:{order.id}",
            )

    @staticmethod
    def run_all_checks(db: Session):
        """Runs every on-demand check - called from the notifications
        list endpoint so opening the notification panel always reflects
        current state, without needing a background scheduler."""
        NotificationService.check_stock_notifications(db)
        NotificationService.check_payment_overdue_notifications(db)

    @staticmethod
    def visible_to(query, user_id: Optional[int], role: str):
        """A notification is visible if it's addressed to this specific
        user, or it's a broadcast (no specific recipient) whose type
        isn't financial - financial broadcasts stay master-only even
        though they have no specific recipient set. The single
        definition of "who can see this notification" - used for the
        notification list itself and, unchanged, for the
        communication search over notification content."""
        own = Notification.recipient_user_id == user_id
        if role in ("master",):
            return query.filter(or_(own, Notification.recipient_user_id.is_(None)))
        operational_broadcast = and_(
            Notification.recipient_user_id.is_(None),
            Notification.notification_type.notin_(FINANCIAL_NOTIFICATION_TYPES),
        )
        return query.filter(or_(own, operational_broadcast))


# --- mention_service.py ---
"""Mention detection.

A comment (task or order) can @mention a user by username - e.g.
"@priya can you check this before Friday". Detected mentions become a
real notification to that specific user (never a broadcast, since a
mention is inherently addressed to one person), via the same
NotificationService.notify() every other notification in this app goes
through - not a separate mention-delivery mechanism.

Deliberately server-side only: matching is done directly against the
Users table and never returns candidate/matched users to the caller, so
this can't be used to enumerate usernames (User listing is already
master-only - see users.py) or leak whether a given username exists.
"""

_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.-]{2,50})")


def extract_mentioned_usernames(text: str) -> List[str]:
    """Case-preserving raw @handles found in the text - deduplicated,
    order preserved. Matching against real accounts happens later, in
    notify_mentions, so this alone never confirms a username exists."""
    seen = []
    for handle in _MENTION_PATTERN.findall(text or ""):
        if handle.lower() not in [s.lower() for s in seen]:
            seen.append(handle)
    return seen


def notify_mentions(db: Session, *, text: str, comment_id: int, source_type: str, entity_type: str,
                     entity_id: int, title: str, action_path: str, excluded_user_id=None) -> int:
    """Resolves @handles in `text` against real, active User accounts
    and fires one MENTION-type notification per match - dedup_key keyed
    on the specific comment + user, so editing/re-fetching a comment
    (or this being called more than once for the same comment) never
    double-notifies the same person for the same mention.
    excluded_user_id skips notifying someone about their own comment
    (e.g. self-mentioning, or replying in a thread where their own
    username appears quoted)."""
    handles = extract_mentioned_usernames(text)
    if not handles:
        return 0
    notified = 0
    for handle in handles:
        user = db.query(User).filter(User.username.ilike(handle), User.is_active.is_(True)).first()
        if not user or user.id == excluded_user_id:
            continue
        NotificationService.notify(
            db, notification_type="MENTION", severity="INFO",
            title=title, message=f"You were mentioned: \"{text[:200]}\"",
            recipient_user_id=user.id, related_entity_type=entity_type, related_entity_id=entity_id,
            action_path=action_path, dedup_key=f"mention:{source_type}:{comment_id}:user:{user.id}",
        )
        notified += 1
    return notified


# --- communication_ai_service.py ---
"""'AI' communication helpers.

Honesty requirement: this app has no real LLM integration for this
module (see chat_service.py's own docstring). Every function here is
plain, deterministic text processing - keyword/heuristic extraction,
not genuine language understanding. Every result this module returns
is labeled "rule-based" so nothing here is ever presented as real AI
reasoning it isn't. If a real LLM integration is added later, this
module's outputs are exactly the kind of thing it would replace - not
a claim this already does it.

None of this sends anything anywhere: summarize/extract/draft are all
read-only analysis of existing comments/activity already stored via the
normal comment/activity endpoints, or a plain string handed back for a
human to review, edit, and send themselves through whatever channel
they already use outside Woodful. There is no external send capability
in this app for this module to call even if it wanted to.
"""

_QUESTION_RE = re.compile(r"\?\s*$")


_ACTION_MARKERS = (
    "please", "need to", "needs to", "todo", "to-do", "to do:", "action:", "follow up", "follow-up",
    "can you", "could you", "will send", "will share", "must", "should", "pending", "waiting on", "asap",
)


@dataclass
class CommunicationEntry:
    """One normalized item from any comment/activity source (task
    comment, order comment, client activity) - the common shape every
    function below operates on, regardless of which table it came
    from."""
    author: str
    text: str
    date: object  # datetime - kept loose to avoid importing every source's date type
    source_type: str  # "task_comment" / "order_comment" / "client_activity"


@dataclass
class CommunicationInsights:
    method: str
    summary: str
    action_items: List[str] = field(default_factory=list)
    unanswered_items: List[str] = field(default_factory=list)
    entry_count: int = 0


def summarize_and_extract(entries: List[CommunicationEntry]) -> CommunicationInsights:
    """Extractive summary + action items + unanswered questions - all
    rule-based (see module docstring). Ordered oldest-first before
    processing, so "unanswered" can mean "no later entry from a
    different author follows this question"."""
    ordered = sorted(entries, key=lambda e: e.date)

    if not ordered:
        return CommunicationInsights(
            method="rule_based_extractive", summary="No communication recorded yet.",
            action_items=[], unanswered_items=[], entry_count=0,
        )

    summary_lines = [f"{e.author}: {e.text.strip()[:160]}" for e in ordered[-5:]]
    summary = (
        f"{len(ordered)} entr{'y' if len(ordered) == 1 else 'ies'} recorded. "
        f"Most recent: " + " | ".join(summary_lines)
    )

    action_items = []
    for e in ordered:
        lowered = e.text.lower()
        if any(marker in lowered for marker in _ACTION_MARKERS):
            action_items.append(f"{e.author}: {e.text.strip()[:200]}")

    unanswered_items = []
    for i, e in enumerate(ordered):
        if not _QUESTION_RE.search(e.text.strip()):
            continue
        answered = any(
            later.author != e.author for later in ordered[i + 1:]
        )
        if not answered:
            unanswered_items.append(f"{e.author}: {e.text.strip()[:200]}")

    return CommunicationInsights(
        method="rule_based_extractive", summary=summary, action_items=action_items,
        unanswered_items=unanswered_items, entry_count=len(ordered),
    )


_DRAFT_TEMPLATES = {
    "follow_up": (
        "Hi {name},\n\nFollowing up on {subject}. Let me know if you have any updates or questions "
        "on your end.\n\nThanks,\n{sender}"
    ),
    "status_update": (
        "Hi {name},\n\nA quick update on {subject}: {detail}\n\nHappy to answer any questions.\n\n"
        "Thanks,\n{sender}"
    ),
    "payment_reminder": (
        "Hi {name},\n\nA gentle reminder regarding the outstanding balance on {subject}. "
        "Please let us know if you have any questions about the payment.\n\nThanks,\n{sender}"
    ),
}


def draft_message(purpose: str, *, name: str, subject: str, sender: str, detail: Optional[str] = None) -> str:
    """A plain template fill-in, not generated text - the same honesty
    boundary as summarize_and_extract above. Returned as a draft only:
    nothing in this app sends it anywhere. External communication
    requires a human to take it from here
    and send it themselves through whatever channel they use outside
    Woodful - this module (and this app) has no send capability to
    bypass that with even if it tried."""
    template = _DRAFT_TEMPLATES.get(purpose)
    if not template:
        raise ValueError(f"Unknown draft purpose: {purpose}")
    return template.format(name=name, subject=subject, sender=sender, detail=detail or "no change since last update")
