from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.modules.communications.models import Notification
from app.modules.inventory.models import Material, Purchase
from app.modules.sales.models import Order
from app.modules.auth.models import User
from app.platform.database.id_generator import generate_business_id

# Notification types whose content is inherently financial - even when
# broadcast (no specific recipient), only master should see these.
# Operational broadcasts (LOW_STOCK, OUT_OF_STOCK, PURCHASE_RECEIVED -
# quantities/materials/suppliers, never a price) are visible to
# everyone, matching "Employee CAN view stock/material information"
# from the access-control brief.
# PURCHASE_RECOMMENDED is a recommendation to spend money on
# a purchase - same financial-commitment sensitivity as PAYMENT_OVERDUE,
# and purchases themselves are already master-only (see purchases.py).
# ESTIMATE_PENDING_RESPONSE is about an Estimate -
# a financial document whose create/update/revise routes are already
# require_role("master") in estimates.py - same tier.
# Lives here (not in the notifications route) so every other place that
# needs the exact same "can this role see this notification" rule -
# the communication search included - imports the one
# definition rather than re-deriving it.
FINANCIAL_NOTIFICATION_TYPES = {"PAYMENT_OVERDUE", "PAYMENT_DUE", "PURCHASE_RECOMMENDED", "ESTIMATE_PENDING_RESPONSE"}


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
        caught and logged, not raised."""
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
        db.commit()
        db.refresh(notification)

        if recipient_email:
            try:
                from app.modules.communications.services.email_service import EmailService
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
        from app.modules.communications.services.email_service import EmailService
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
        """Called directly from StockService.record_purchase - a real
        event as it happens, not a periodic scan."""
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
