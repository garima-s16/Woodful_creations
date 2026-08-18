from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.material import Material
from app.models.order import Order
from app.models.purchase import Purchase
from app.utils.id_generator import generate_short_id


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
               dedup_key: Optional[str] = None) -> Notification:
        """Creates a notification, unless an unread one with the same
        dedup_key already exists (Section 46's explicit "do not create
        the same notification repeatedly on every dashboard refresh")."""
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
            business_id=generate_short_id(),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def check_stock_notifications(db: Session):
        """LOW_STOCK / OUT_OF_STOCK, driven by the same Material.stock_status
        every other part of the app already uses - not a separately
        re-derived threshold check."""
        materials = db.query(Material).all()
        for m in materials:
            status = m.stock_status
            if status == "OUT OF STOCK":
                NotificationService.notify(
                    db, notification_type="OUT_OF_STOCK", severity="CRITICAL",
                    title=f"{m.name} is out of stock",
                    message=f"{m.name} ({m.material_code}) has 0 {m.unit} remaining.",
                    related_entity_type="material", related_entity_id=m.id,
                    action_path=f"/materials/{m.id}", dedup_key=f"out_of_stock:material:{m.id}",
                )
            elif status == "LOW STOCK":
                NotificationService.notify(
                    db, notification_type="LOW_STOCK", severity="WARNING",
                    title=f"{m.name} is running low",
                    message=f"{m.name} ({m.material_code}) is at {m.current_stock} {m.unit}, "
                            f"at or below the reorder level of {m.minimum_stock} {m.unit}.",
                    related_entity_type="material", related_entity_id=m.id,
                    action_path=f"/materials/{m.id}", dedup_key=f"low_stock:material:{m.id}",
                )

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
