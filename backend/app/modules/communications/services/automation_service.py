"""Automation.

EVENT -> CONDITION -> ACTION, built around real business events already
tracked elsewhere in the app (an overdue DailyTask, a Material below its
reorder level, a Purchase whose delivery is due, an overdue Order balance,
a missed Milestone, a Blocked ProductionJob) - never a fabricated/demo
trigger.

Architecture note (same one NotificationService already documents): this
app has no background job scheduler installed (no Celery/APScheduler in
requirements.txt). Automation rules therefore run on-demand - wired into
the notifications endpoints (so opening the notification panel evaluates
current state, exactly like NotificationService.run_all_checks already
does) and exposed via POST /api/automation/run for an external
scheduler (cron, a hosting platform's scheduled task, etc.) to call
periodically. dedup_key is what makes both call sites safe to invoke
repeatedly without creating duplicate notifications or duplicate
AutomationLog rows - the same mechanism Notification.dedup_key already
uses, extended here to also cover the audit trail.

Actions: every rule's action is either (a) a notification - informational,
never a change to business data - or (b) a recommendation surfaced via
notification (low stock -> recommend a purchase quantity, logged with
status PROPOSED) - never a silently-created Purchase, Payment, or stock
adjustment. Sensitive actions must be proposed, not
auto-executed, and no existing Woodful business rule grants blanket
auto-purchase/auto-payment authority, so every rule here stops at
"recommend/notify".
"""
import calendar
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.communications.models import Notification, AutomationLog
from app.modules.operations.models import DailyTask
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Milestone
from app.modules.operations.models import ProductionJob
from app.modules.clients.models import ClientActivity
from app.modules.sales.models import Estimate
from app.modules.hr.models import Leave, SalaryAdvance, SalarySlip
from app.modules.auth.models import User
from app.modules.communications.services.notification_service import NotificationService

DELIVERY_APPROACHING_WINDOW_DAYS = 3
# Same "configurable-in-spirit, constant-in-practice" approach already
# used for DELIVERY_APPROACHING_WINDOW_DAYS above - this app has no
# Setting-backed automation threshold anywhere to plug into, so a new
# per-rule Setting row would be new architecture, not a gap fix.
MILESTONE_DEADLINE_APPROACHING_WINDOW_DAYS = 5
# An estimate left in "sent" (awaiting the client's response) with no
# update for this many days is treated as a pending action worth
# surfacing - mirrors the same "genuinely stale, not merely open"
# framing check_purchase_delivery_approaching already uses via
# expected_delivery_date.
PENDING_ESTIMATE_RESPONSE_STALE_DAYS = 5
# Grace window after a payroll month's last calendar day before a
# still-"draft" SalarySlip is treated as a genuine finalization issue -
# mirrors PENDING_ESTIMATE_RESPONSE_STALE_DAYS's "genuinely stale, not
# merely open yet" framing (payroll for the month just ended isn't an
# issue on day one of the next month).
PAYROLL_FINALIZATION_GRACE_DAYS = 5
CONDITION_SUMMARY_MAX = 2000
ERROR_MESSAGE_MAX = 2000


class AutomationService:
    RULE_TASK_OVERDUE = "task_overdue"
    RULE_LOW_STOCK_RECOMMENDATION = "low_stock_purchase_recommendation"
    RULE_ORDER_AT_RISK_MATERIAL_SHORTAGE = "order_at_risk_material_shortage"
    RULE_DELIVERY_RISK_CRITICAL = "delivery_risk_critical"
    RULE_PURCHASE_DELIVERY_APPROACHING = "purchase_delivery_approaching"
    RULE_PAYMENT_OVERDUE = "payment_overdue"
    RULE_PROJECT_DELAYED = "project_delayed"
    RULE_PRODUCTION_BLOCKED = "production_blocked"
    RULE_FOLLOW_UP_DUE = "follow_up_due"
    RULE_PENDING_ESTIMATE_RESPONSE = "pending_estimate_response"
    RULE_PROJECT_DEADLINE_APPROACHING = "project_deadline_approaching"
    RULE_OPERATIONAL_SUMMARY = "operational_summary"
    RULE_PENDING_LEAVE_APPROVAL = "pending_leave_approval"
    RULE_PENDING_SALARY_ADVANCE_APPROVAL = "pending_salary_advance_approval"
    RULE_PAYROLL_FINALIZATION_OVERDUE = "payroll_finalization_overdue"

    RULES = [
        {"key": RULE_TASK_OVERDUE, "event": "DailyTask past its date and not DONE",
         "action": "Notify the assigned employee's account"},
        {"key": RULE_LOW_STOCK_RECOMMENDATION, "event": "Material at or below its reorder level",
         "action": "Recommend a purchase quantity (master only) - proposes, never auto-creates a Purchase"},
        {"key": RULE_ORDER_AT_RISK_MATERIAL_SHORTAGE, "event": "An open order's real material shortage - "
         "against its own BOM, current stock, pending purchases and other orders' reservations - "
         "not just a material below its reorder level (Family 130 - reuses "
         "StockService.calculate_at_risk_orders, the same calculation already shown on the dashboard, "
         "the daily-tasks list and the AI chatbot, so this proactive notification can never disagree "
         "with what those other surfaces show)", "action": "Notify (broadcast) with a link to the order"},
        {"key": RULE_DELIVERY_RISK_CRITICAL, "event": "An order's delivery risk reaches CRITICAL "
         "(P0.50) - reuses OrderService.bulk_attention_flags exactly, the same classification already "
         "shown on the Orders List and Dashboard, so this can never disagree with what a Master sees "
         "on-screen. Deliberately does NOT fire for WATCH or AT_RISK - only the most severe level, "
         "to avoid the notification noise section 38 explicitly warns against",
         "action": "Notify (broadcast) with a link to the order"},
        {"key": RULE_PURCHASE_DELIVERY_APPROACHING, "event": "Purchase not yet fully received, delivery due soon",
         "action": "Notify master"},
        {"key": RULE_PAYMENT_OVERDUE, "event": "Order balance outstanding 30+ days after order date",
         "action": "Notify master (reuses NotificationService's existing check)"},
        {"key": RULE_PROJECT_DELAYED, "event": "Milestone target date passed, not marked complete",
         "action": "Notify (broadcast) with a link to the project"},
        {"key": RULE_PRODUCTION_BLOCKED, "event": "ProductionJob status is Blocked",
         "action": "Notify the assigned operator's account"},
        {"key": RULE_FOLLOW_UP_DUE, "event": "ClientActivity.follow_up_date due/overdue and not done",
         "action": "Notify (broadcast) with a link to the client"},
        {"key": RULE_PENDING_ESTIMATE_RESPONSE, "event": "Estimate left in 'sent' status with no update for "
         f"{PENDING_ESTIMATE_RESPONSE_STALE_DAYS}+ days", "action": "Notify master - financial document, "
         "same sensitivity tier as PURCHASE_RECOMMENDED"},
        {"key": RULE_PROJECT_DEADLINE_APPROACHING, "event": "Milestone target date within "
         f"{MILESTONE_DEADLINE_APPROACHING_WINDOW_DAYS} day(s) and not yet passed/complete",
         "action": "Notify (broadcast) with a link to the project - distinct from project_delayed, "
         "which only fires once the date has passed"},
        {"key": RULE_OPERATIONAL_SUMMARY, "event": "Daily rollup of overdue tasks, approaching project "
         "deadlines, blocked production, low stock, pending purchases and pending follow-ups",
         "action": "Notify (broadcast) - counts only, no financial amounts, so safe for every role"},
        {"key": RULE_PENDING_LEAVE_APPROVAL, "event": "Leave request left in 'Pending' status",
         "action": "Notify (broadcast) with a link to the leaves list - matches leaves.py's own "
         "existing get_current_user visibility, not master-only"},
        {"key": RULE_PENDING_SALARY_ADVANCE_APPROVAL, "event": "Salary advance request left in "
         "'Pending' status", "action": "Notify master - reveals a requested amount, same financial "
         "sensitivity tier as PURCHASE_RECOMMENDED/ESTIMATE_PENDING_RESPONSE"},
        {"key": RULE_PAYROLL_FINALIZATION_OVERDUE, "event": "SalarySlip still 'draft' more than "
         f"{PAYROLL_FINALIZATION_GRACE_DAYS} day(s) after its own pay-period month fully ended",
         "action": "Notify master - payroll processing status, same financial sensitivity tier as "
         "the salary advance rule above"},
    ]

    # ---------------------------------------------------------------- #
    # Shared helpers
    # ---------------------------------------------------------------- #
    @staticmethod
    def _log(db: Session, *, rule_key: str, trigger_event: str, condition_summary: str, action_taken: str,
              status: str, entity_type: Optional[str] = None, entity_id: Optional[int] = None,
              notification_id: Optional[int] = None, dedup_key: Optional[str] = None,
              error_message: Optional[str] = None) -> AutomationLog:
        entry = AutomationLog(
            rule_key=rule_key, trigger_event=trigger_event,
            condition_summary=condition_summary[:CONDITION_SUMMARY_MAX],
            action_taken=action_taken, status=status,
            related_entity_type=entity_type, related_entity_id=entity_id,
            notification_id=notification_id, dedup_key=dedup_key,
            error_message=error_message[:ERROR_MESSAGE_MAX] if error_message else None,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def _notify_and_log(db: Session, *, rule_key: str, trigger_event: str, condition_summary: str,
                         notification_type: str, severity: str, title: str, message: str,
                         entity_type: str, entity_id: Optional[int], dedup_key: str, action_taken: str,
                         action_path: Optional[str] = None, recipient_user_id: Optional[int] = None,
                         log_status: str = "SUCCESS") -> Optional[AutomationLog]:
        """The shared ACTION primitive for every notify-based rule below.
        Reuses NotificationService.notify() - the one place a Notification
        row is ever created in this app - rather than writing to the
        notifications table directly. Only adds an AutomationLog row when
        notify() actually created a brand-new notification: if an unread
        one with this dedup_key already existed, the situation is already
        being tracked, and logging it again here would be exactly the
        repeated noise automation must not create."""
        existing = db.query(Notification.id).filter(
            Notification.dedup_key == dedup_key, Notification.is_read.is_(False)
        ).first()
        pre_existing_id = existing[0] if existing else None

        notification = NotificationService.notify(
            db, notification_type=notification_type, severity=severity, title=title, message=message,
            recipient_user_id=recipient_user_id, related_entity_type=entity_type, related_entity_id=entity_id,
            action_path=action_path, dedup_key=dedup_key,
        )
        if notification.id == pre_existing_id:
            return None  # already tracked - no new action, nothing new to log

        return AutomationService._log(
            db, rule_key=rule_key, trigger_event=trigger_event, condition_summary=condition_summary,
            action_taken=action_taken, status=log_status, entity_type=entity_type, entity_id=entity_id,
            notification_id=notification.id, dedup_key=dedup_key,
        )

    @staticmethod
    def _recipients_for_employees(db: Session, employee_ids) -> dict:
        """The same Employee -> User resolution already used for task
        assignment/completion notifications (see daily_tasks.py,
        chat_service.py) - not a new lookup convention. Resolves every
        needed employee_id -> user_id mapping in a single query instead
        of one query per row, for callers that loop over many rows
        (check_task_overdue, check_production_blocked). Returns
        {employee_id: user_id}; an employee_id with no linked login
        account is simply absent from the result, not a None entry."""
        ids = {i for i in employee_ids if i}
        if not ids:
            return {}
        return {
            u.employee_id: u.id
            for u in db.query(User).filter(User.employee_id.in_(ids)).all()
        }

    # ---------------------------------------------------------------- #
    # Rule: Task overdue -> notify assigned user
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_task_overdue(db: Session, trigger_event: str = "on_demand_check") -> None:
        today = datetime.utcnow().date()
        tasks = db.query(DailyTask).filter(DailyTask.status != "DONE").all()
        recipients = AutomationService._recipients_for_employees(db, (t.employee_id for t in tasks))
        for task in tasks:
            dedup_key = f"automation:task_overdue:{task.id}"
            try:
                if not task.date or task.date.date() >= today:
                    continue
                days_overdue = (today - task.date.date()).days
                recipient_user_id = recipients.get(task.employee_id)
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_TASK_OVERDUE, trigger_event=trigger_event,
                    condition_summary=(
                        f"Task {task.task_code} was due {task.date.date().isoformat()} "
                        f"({days_overdue} day(s) ago) and is still '{task.status}'."
                    ),
                    notification_type="TASK_OVERDUE", severity="WARNING",
                    title=f"Task overdue - {task.task_code}",
                    message=f"\"{task.task_description}\" was due on {task.date.strftime('%d %b %Y')} "
                            f"and is still marked {task.status}.",
                    entity_type="task", entity_id=task.id, dedup_key=dedup_key,
                    action_taken="notify:TASK_OVERDUE", action_path=f"/daily-tasks/{task.id}",
                    recipient_user_id=recipient_user_id,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_TASK_OVERDUE, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating task id={task.id}.",
                    action_taken="notify:TASK_OVERDUE", status="FAILED",
                    entity_type="task", entity_id=task.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Stock below threshold -> recommend a purchase (never auto-created)
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_low_stock_purchase_recommendations(db: Session, trigger_event: str = "on_demand_check") -> None:
        materials = db.query(Material).filter(Material.is_active.is_(True)).all()
        for m in materials:
            dedup_key = f"automation:purchase_recommended:material:{m.id}"
            try:
                status = m.stock_status
                if status not in ("LOW STOCK", "OUT OF STOCK"):
                    continue
                recommended_qty = float(m.minimum_stock or 0) - float(m.current_stock or 0)
                if recommended_qty <= 0:
                    continue  # nothing sane to recommend (e.g. minimum_stock itself is 0)
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_LOW_STOCK_RECOMMENDATION, trigger_event=trigger_event,
                    condition_summary=(
                        f"{m.name} ({m.material_code}) is at {m.current_stock} {m.unit}, at or below the "
                        f"reorder level of {m.minimum_stock} {m.unit}."
                    ),
                    notification_type="PURCHASE_RECOMMENDED",
                    severity="CRITICAL" if status == "OUT OF STOCK" else "WARNING",
                    title=f"Recommended: reorder {m.name}",
                    message=(
                        f"{m.name} ({m.material_code}) is {status.lower()}. Recommend purchasing at least "
                        f"{recommended_qty:g} {m.unit} to return to the reorder level of {m.minimum_stock} {m.unit}. "
                        f"This is a recommendation only - no purchase has been created."
                    ),
                    entity_type="material", entity_id=m.id, dedup_key=dedup_key,
                    action_taken="recommend_purchase", action_path=f"/purchases/new?material_id={m.id}",
                    log_status="PROPOSED",
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_LOW_STOCK_RECOMMENDATION, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating material id={m.id}.",
                    action_taken="recommend_purchase", status="FAILED",
                    entity_type="material", entity_id=m.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Order at risk of a material shortage (Family 130) -> notify
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_order_at_risk_material_shortage(db: Session, trigger_event: str = "on_demand_check") -> None:
        """Complements check_low_stock_purchase_recommendations above:
        that rule is material-centric ("Plywood is low, buy more") and
        fires even for a shortage that threatens nothing yet. This rule
        is order-centric - it only fires when a real, current order is
        actually blocked, and names which one, matching Family 130
        section 8's target: "explain which order is at risk, why, and
        what material causes the risk" rather than leaving that
        connection for someone to work out by hand."""
        from app.modules.inventory.stock_service import StockService
        try:
            at_risk_orders = StockService.calculate_at_risk_orders(db)
        except Exception as exc:
            db.rollback()
            AutomationService._log(
                db, rule_key=AutomationService.RULE_ORDER_AT_RISK_MATERIAL_SHORTAGE, trigger_event=trigger_event,
                condition_summary="Failed while calculating at-risk orders.",
                action_taken="notify:ORDER_AT_RISK", status="FAILED", error_message=str(exc),
            )
            return

        for row in at_risk_orders:
            dedup_key = f"automation:order_at_risk:{row['order_id']}"
            try:
                top_material = row["materials"][0]
                extra = f" and {row['total_shortage_lines'] - 1} other material(s)" if row["total_shortage_lines"] > 1 else ""
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_ORDER_AT_RISK_MATERIAL_SHORTAGE, trigger_event=trigger_event,
                    condition_summary=(
                        f"Order {row['order_code']} ({row['client_name'] or 'client'}) is short "
                        f"{top_material['shortage']:g} {top_material['unit']} of {top_material['material_name']}{extra}."
                    ),
                    notification_type="ORDER_AT_RISK", severity="WARNING",
                    title=f"Order at risk - {row['order_code']}",
                    message=(
                        f"{row['order_code']} ({row['client_name'] or 'client'}) is short "
                        f"{top_material['shortage']:g} {top_material['unit']} of {top_material['material_name']}{extra}. "
                        f"This is the current stock/reservation picture - no purchase has been created automatically."
                    ),
                    entity_type="order", entity_id=row["order_id"], dedup_key=dedup_key,
                    action_taken="notify:ORDER_AT_RISK", action_path=f"/orders/{row['order_id']}",
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_ORDER_AT_RISK_MATERIAL_SHORTAGE, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating order id={row.get('order_id')}.",
                    action_taken="notify:ORDER_AT_RISK", status="FAILED",
                    entity_type="order", entity_id=row.get("order_id"), dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Delivery risk reaches CRITICAL (P0.50) -> notify
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_delivery_risk_critical(db: Session, trigger_event: str = "on_demand_check") -> None:
        """Complements check_order_at_risk_material_shortage above: that
        rule fires on a material shortage specifically. This rule fires
        on the order's overall delivery risk reaching CRITICAL (P0.50's
        4-level model) - a real delivery commitment already missed and
        still open, or imminent with a genuine blocker - regardless of
        which specific signal caused it. Reuses
        OrderService.bulk_attention_flags exactly, the same bounded,
        batched calculation already backing the Orders List's
        attention_risk_level and the Dashboard's delivery_risk_summary,
        so this can never disagree with what a Master sees on-screen.
        Deliberately does not fire for WATCH or AT_RISK - only the most
        severe level, to avoid the notification noise section 38
        explicitly warns against."""
        from app.modules.sales.models import Order
        try:
            active_order_ids = [
                r[0] for r in db.query(Order.id).filter(Order.project_status != "Completed").all()
            ]
            if not active_order_ids:
                return
            flags = OrderService.bulk_attention_flags(db, active_order_ids)
        except Exception as exc:
            db.rollback()
            AutomationService._log(
                db, rule_key=AutomationService.RULE_DELIVERY_RISK_CRITICAL, trigger_event=trigger_event,
                condition_summary="Failed while calculating delivery risk.",
                action_taken="notify:DELIVERY_RISK_CRITICAL", status="FAILED", error_message=str(exc),
            )
            return

        orders_by_id = {o.id: o for o in db.query(Order).filter(Order.id.in_(active_order_ids)).all()}
        for order_id, flag in flags.items():
            if flag["risk_level"] != "CRITICAL":
                continue
            dedup_key = f"automation:delivery_risk_critical:{order_id}"
            try:
                order = orders_by_id.get(order_id)
                if not order:
                    continue
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_DELIVERY_RISK_CRITICAL, trigger_event=trigger_event,
                    condition_summary=f"{order.order_code}'s delivery risk is CRITICAL: {flag['reason']}",
                    notification_type="DELIVERY_RISK_CRITICAL", severity="CRITICAL",
                    title=f"Delivery risk CRITICAL - {order.order_code}",
                    message=f"{order.order_code} is at CRITICAL delivery risk: {flag['reason']}",
                    entity_type="order", entity_id=order.id, dedup_key=dedup_key,
                    action_taken="notify:DELIVERY_RISK_CRITICAL", action_path=f"/orders/{order.id}",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_DELIVERY_RISK_CRITICAL, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating order id={order_id}.",
                    action_taken="notify:DELIVERY_RISK_CRITICAL", status="FAILED",
                    entity_type="order", entity_id=order_id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Purchase delivery approaching -> notify master
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_purchase_delivery_approaching(db: Session, trigger_event: str = "on_demand_check") -> None:
        now = datetime.utcnow()
        window_end = now + timedelta(days=DELIVERY_APPROACHING_WINDOW_DAYS)
        purchases = db.query(Purchase).filter(
            Purchase.receipt_status.in_(["Ordered", "Partially Received"]),
            Purchase.expected_delivery_date.isnot(None),
            Purchase.expected_delivery_date <= window_end,
        ).all()
        for p in purchases:
            dedup_key = f"automation:purchase_delivery:{p.id}"
            try:
                days_until = (p.expected_delivery_date.date() - now.date()).days
                if days_until < 0:
                    timing = f"was expected {abs(days_until)} day(s) ago and hasn't been fully received yet"
                    severity = "CRITICAL"
                elif days_until == 0:
                    timing = "is expected today"
                    severity = "WARNING"
                else:
                    timing = f"is expected in {days_until} day(s)"
                    severity = "WARNING"
                material_name = p.material.name if p.material else "Material"
                supplier_name = p.supplier.name if p.supplier else "Supplier"
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PURCHASE_DELIVERY_APPROACHING, trigger_event=trigger_event,
                    condition_summary=(
                        f"Purchase {p.purchase_code} ({p.receipt_status}) from {supplier_name} {timing}."
                    ),
                    notification_type="PURCHASE_DELIVERY_APPROACHING", severity=severity,
                    title=f"Delivery {('overdue' if days_until < 0 else 'approaching')} - {p.purchase_code}",
                    message=f"{p.quantity} {p.unit} of {material_name} from {supplier_name} ({p.purchase_code}) {timing}.",
                    entity_type="purchase", entity_id=p.id, dedup_key=dedup_key,
                    action_taken="notify:PURCHASE_DELIVERY_APPROACHING",
                    action_path=f"/purchases/{p.id}",
                    recipient_user_id=None,  # purchases are master-only; broadcast reaches every master
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PURCHASE_DELIVERY_APPROACHING, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating purchase id={p.id}.",
                    action_taken="notify:PURCHASE_DELIVERY_APPROACHING", status="FAILED",
                    entity_type="purchase", entity_id=p.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Payment overdue -> notify master
    # Reuses NotificationService.check_payment_overdue_notifications
    # (the existing, single source of truth for "overdue") rather than a
    # second independently-derived condition. Diffs the notification set
    # before/after so each newly-created notification still gets its own
    # traceable AutomationLog row.
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_payment_overdue(db: Session, trigger_event: str = "on_demand_check") -> None:
        before_ids = {row[0] for row in db.query(Notification.id)
                      .filter(Notification.notification_type == "PAYMENT_OVERDUE").all()}
        try:
            NotificationService.check_payment_overdue_notifications(db)
        except Exception as exc:
            db.rollback()
            AutomationService._log(
                db, rule_key=AutomationService.RULE_PAYMENT_OVERDUE, trigger_event=trigger_event,
                condition_summary="Failed while checking overdue payments.",
                action_taken="notify:PAYMENT_OVERDUE", status="FAILED", error_message=str(exc),
            )
            return

        query = db.query(Notification).filter(Notification.notification_type == "PAYMENT_OVERDUE")
        if before_ids:
            query = query.filter(~Notification.id.in_(before_ids))
        for n in query.all():
            AutomationService._log(
                db, rule_key=AutomationService.RULE_PAYMENT_OVERDUE, trigger_event=trigger_event,
                condition_summary=n.message, action_taken="notify:PAYMENT_OVERDUE", status="SUCCESS",
                entity_type=n.related_entity_type, entity_id=n.related_entity_id,
                notification_id=n.id, dedup_key=n.dedup_key,
            )

    # ---------------------------------------------------------------- #
    # Rule: Project delayed -> notify (broadcast, links to the order)
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_project_delayed(db: Session, trigger_event: str = "on_demand_check") -> None:
        now = datetime.utcnow()
        milestones = db.query(Milestone).filter(
            Milestone.completed_date.is_(None), Milestone.target_date.isnot(None), Milestone.target_date < now,
        ).all()
        for ms in milestones:
            dedup_key = f"automation:project_delayed:milestone:{ms.id}"
            try:
                order = ms.order
                if not order:
                    continue
                days_late = (now.date() - ms.target_date.date()).days
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PROJECT_DELAYED, trigger_event=trigger_event,
                    condition_summary=(
                        f"Milestone '{ms.name}' on {order.order_code} was due {ms.target_date.date().isoformat()} "
                        f"({days_late} day(s) ago) and is not marked complete."
                    ),
                    notification_type="PROJECT_DELAYED", severity="WARNING",
                    title=f"Project delayed - {order.order_code}",
                    message=(
                        f"Milestone \"{ms.name}\" for {order.order_code} was due on "
                        f"{ms.target_date.strftime('%d %b %Y')} and hasn't been marked complete "
                        f"({days_late} day(s) late)."
                    ),
                    entity_type="order", entity_id=order.id, dedup_key=dedup_key,
                    action_taken="notify:PROJECT_DELAYED", action_path=f"/orders/{order.id}",
                    recipient_user_id=None,  # Order has no linked "responsible user" field - broadcast
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PROJECT_DELAYED, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating milestone id={ms.id}.",
                    action_taken="notify:PROJECT_DELAYED", status="FAILED",
                    entity_type="milestone", entity_id=ms.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Production blocked -> surface action to the assigned operator
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_production_blocked(db: Session, trigger_event: str = "on_demand_check") -> None:
        jobs = db.query(ProductionJob).filter(ProductionJob.status == "Blocked").all()
        recipients = AutomationService._recipients_for_employees(db, (j.employee_id for j in jobs))
        for job in jobs:
            dedup_key = f"automation:production_blocked:{job.id}"
            try:
                reason = job.blocker_reason or "no reason given"
                recipient_user_id = recipients.get(job.employee_id)
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PRODUCTION_BLOCKED, trigger_event=trigger_event,
                    condition_summary=f"Production job {job.job_code} is Blocked: {reason}.",
                    notification_type="PRODUCTION_BLOCKED", severity="CRITICAL",
                    title=f"Production blocked - {job.job_code}",
                    message=f"Job {job.job_code} ({job.operation or 'operation'}) is blocked: {reason}.",
                    entity_type="production_job", entity_id=job.id, dedup_key=dedup_key,
                    action_taken="notify:PRODUCTION_BLOCKED", action_path=f"/production/{job.id}",
                    recipient_user_id=recipient_user_id,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PRODUCTION_BLOCKED, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating production job id={job.id}.",
                    action_taken="notify:PRODUCTION_BLOCKED", status="FAILED",
                    entity_type="production_job", entity_id=job.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Follow-up due/overdue -> notify (broadcast, links to client)
    # Reuses the exact condition chat_operations._follow_up_suggestions
    # already established (follow_up_date <= now, follow_up_done is
    # False) - not a separately-invented "what counts as due" rule.
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_follow_up_due(db: Session, trigger_event: str = "on_demand_check") -> None:
        now = datetime.utcnow()
        due = db.query(ClientActivity).filter(
            ClientActivity.follow_up_date.isnot(None), ClientActivity.follow_up_date <= now,
            ClientActivity.follow_up_done.is_(False),
        ).all()
        for activity in due:
            dedup_key = f"automation:follow_up_due:{activity.id}"
            try:
                client = activity.client
                if not client:
                    continue
                days = (now.date() - activity.follow_up_date.date()).days
                timing = "is due today" if days <= 0 else f"is {days} day(s) overdue"
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_FOLLOW_UP_DUE, trigger_event=trigger_event,
                    condition_summary=(
                        f"Follow-up on {client.name} (logged {activity.activity_type}) {timing}."
                    ),
                    notification_type="FOLLOW_UP_DUE", severity="WARNING" if days > 0 else "INFO",
                    title=f"Follow-up due - {client.name}",
                    message=f"A follow-up with {client.name} {timing}: {activity.summary[:150]}",
                    entity_type="client", entity_id=client.id, dedup_key=dedup_key,
                    action_taken="notify:FOLLOW_UP_DUE", action_path=f"/clients/{client.id}",
                    recipient_user_id=None,  # ClientActivity has no "responsible user" field - broadcast
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_FOLLOW_UP_DUE, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating client_activity id={activity.id}.",
                    action_taken="notify:FOLLOW_UP_DUE", status="FAILED",
                    entity_type="client_activity", entity_id=activity.id, dedup_key=dedup_key,
                    error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Estimate pending client response -> notify master
    # An estimate is a financial document (create/update/revise are
    # already require_role("master") in estimates.py); the notification
    # type is financial-tier so it stays out of a non-master's broadcast
    # feed, matching PURCHASE_RECOMMENDED.
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_pending_estimate_response(db: Session, trigger_event: str = "on_demand_check") -> None:
        cutoff = datetime.utcnow() - timedelta(days=PENDING_ESTIMATE_RESPONSE_STALE_DAYS)
        estimates = db.query(Estimate).filter(
            Estimate.status == "sent", Estimate.updated_at < cutoff,
        ).all()
        for est in estimates:
            dedup_key = f"automation:pending_estimate_response:{est.id}"
            try:
                client = est.client
                days = (datetime.utcnow().date() - est.updated_at.date()).days
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PENDING_ESTIMATE_RESPONSE, trigger_event=trigger_event,
                    condition_summary=(
                        f"Estimate {est.estimate_code} has been 'sent' with no update for {days} day(s)."
                    ),
                    notification_type="ESTIMATE_PENDING_RESPONSE", severity="WARNING",
                    title=f"Awaiting response - {est.estimate_code}",
                    message=(
                        f"Estimate {est.estimate_code} for {client.name if client else 'client'} was sent "
                        f"{days} day(s) ago and hasn't been marked approved or rejected yet."
                    ),
                    entity_type="estimate", entity_id=est.id, dedup_key=dedup_key,
                    action_taken="notify:ESTIMATE_PENDING_RESPONSE", action_path=f"/estimates/{est.id}",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PENDING_ESTIMATE_RESPONSE, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating estimate id={est.id}.",
                    action_taken="notify:ESTIMATE_PENDING_RESPONSE", status="FAILED",
                    entity_type="estimate", entity_id=est.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Project deadline approaching -> notify (broadcast)
    # Distinct from check_project_delayed: fires BEFORE target_date
    # passes, within a fixed window, instead of after. A milestone
    # already inside the window gets exactly one approaching
    # notification (dedup_key), then check_project_delayed takes over
    # once the date actually passes - the two rules never both notify
    # for the same still-open condition on the same day.
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_project_deadline_approaching(db: Session, trigger_event: str = "on_demand_check") -> None:
        now = datetime.utcnow()
        window_end = now + timedelta(days=MILESTONE_DEADLINE_APPROACHING_WINDOW_DAYS)
        milestones = db.query(Milestone).filter(
            Milestone.completed_date.is_(None), Milestone.target_date.isnot(None),
            Milestone.target_date >= now, Milestone.target_date <= window_end,
        ).all()
        for ms in milestones:
            dedup_key = f"automation:project_deadline_approaching:milestone:{ms.id}"
            try:
                order = ms.order
                if not order:
                    continue
                days_left = (ms.target_date.date() - now.date()).days
                timing = "is due today" if days_left <= 0 else f"is due in {days_left} day(s)"
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PROJECT_DEADLINE_APPROACHING, trigger_event=trigger_event,
                    condition_summary=(
                        f"Milestone '{ms.name}' on {order.order_code} {timing} "
                        f"({ms.target_date.date().isoformat()}) and is not marked complete."
                    ),
                    notification_type="PROJECT_DEADLINE_APPROACHING", severity="INFO",
                    title=f"Deadline approaching - {order.order_code}",
                    message=(
                        f"Milestone \"{ms.name}\" for {order.order_code} {timing} "
                        f"({ms.target_date.strftime('%d %b %Y')})."
                    ),
                    entity_type="order", entity_id=order.id, dedup_key=dedup_key,
                    action_taken="notify:PROJECT_DEADLINE_APPROACHING", action_path=f"/orders/{order.id}",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PROJECT_DEADLINE_APPROACHING, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating milestone id={ms.id}.",
                    action_taken="notify:PROJECT_DEADLINE_APPROACHING", status="FAILED",
                    entity_type="milestone", entity_id=ms.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Pending leave approval -> notify (broadcast)
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_pending_leave_approval(db: Session, trigger_event: str = "on_demand_check") -> None:
        """Approval Intelligence (Family 131 section 23): a Leave request
        left in 'Pending' is a real, queryable approval-required
        condition (Leave.status - see app/modules/hr/models.py), not a
        fabricated workflow. Broadcast, matching leaves.py's own existing
        visibility (list_leaves is open to any authenticated user, not
        master-only) - only the approve/reject action itself is
        master-only (see leaves.py's require_role("master"))."""
        leaves = db.query(Leave).filter(Leave.status == "Pending").all()
        for leave in leaves:
            dedup_key = f"automation:pending_leave_approval:{leave.id}"
            try:
                employee_name = leave.employee.name if leave.employee else "An employee"
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PENDING_LEAVE_APPROVAL, trigger_event=trigger_event,
                    condition_summary=(
                        f"Leave request (id={leave.id}) for {employee_name} - {leave.leave_type}, "
                        f"{leave.days} day(s) - is still 'Pending'."
                    ),
                    notification_type="LEAVE_APPROVAL_REQUIRED", severity="INFO",
                    title=f"Leave approval required - {employee_name}",
                    message=(
                        f"{employee_name} requested {leave.days} day(s) of {leave.leave_type} leave "
                        f"starting {leave.start_date.strftime('%d %b %Y')}, awaiting approval."
                    ),
                    entity_type="leave", entity_id=leave.id, dedup_key=dedup_key,
                    action_taken="notify:LEAVE_APPROVAL_REQUIRED", action_path="/leaves",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PENDING_LEAVE_APPROVAL, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating leave id={leave.id}.",
                    action_taken="notify:LEAVE_APPROVAL_REQUIRED", status="FAILED",
                    entity_type="leave", entity_id=leave.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Pending salary advance approval -> notify master
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_pending_salary_advance_approval(db: Session, trigger_event: str = "on_demand_check") -> None:
        """A SalaryAdvance request left in 'Pending' (see
        app/modules/hr/models.py) is a real approval-required condition.
        Master-only visibility (not broadcast) - the message states a
        requested amount, the same financial-commitment sensitivity
        FINANCIAL_NOTIFICATION_TYPES already assigns to PURCHASE_RECOMMENDED
        and ESTIMATE_PENDING_RESPONSE."""
        advances = db.query(SalaryAdvance).filter(SalaryAdvance.status == "Pending").all()
        for adv in advances:
            dedup_key = f"automation:pending_salary_advance_approval:{adv.id}"
            try:
                employee_name = adv.employee.name if adv.employee else "An employee"
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PENDING_SALARY_ADVANCE_APPROVAL, trigger_event=trigger_event,
                    condition_summary=(
                        f"Salary advance request (id={adv.id}) for {employee_name} - "
                        f"Rs {float(adv.requested_amount):,.2f} - is still 'Pending'."
                    ),
                    notification_type="SALARY_ADVANCE_APPROVAL_REQUIRED", severity="WARNING",
                    title=f"Advance approval required - {employee_name}",
                    message=(
                        f"{employee_name} requested a salary advance of Rs {float(adv.requested_amount):,.2f} "
                        f"on {adv.request_date.strftime('%d %b %Y')}, awaiting approval."
                    ),
                    entity_type="salary_advance", entity_id=adv.id, dedup_key=dedup_key,
                    action_taken="notify:SALARY_ADVANCE_APPROVAL_REQUIRED", action_path="/salary-advances",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PENDING_SALARY_ADVANCE_APPROVAL, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating salary advance id={adv.id}.",
                    action_taken="notify:SALARY_ADVANCE_APPROVAL_REQUIRED", status="FAILED",
                    entity_type="salary_advance", entity_id=adv.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Payroll issue -> a draft SalarySlip whose own pay-period
    # month has already ended -> notify master
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_payroll_finalization_overdue(db: Session, trigger_event: str = "on_demand_check") -> None:
        """Payroll Issue (Family 131 section 23): a SalarySlip left in
        'draft' after its own pay-period month has fully ended (plus a
        short grace window - see PAYROLL_FINALIZATION_GRACE_DAYS) is a
        genuine operational finding, derived only from SalarySlip.month/
        year/status (see app/modules/hr/models.py) - never a fabricated
        payroll risk score. month is free text (e.g. "August" - see
        SalarySlipsPage's own placeholder); unparseable values are
        skipped rather than guessed at."""
        now = datetime.utcnow()
        slips = db.query(SalarySlip).filter(SalarySlip.status == "draft").all()
        for slip in slips:
            dedup_key = f"automation:payroll_finalization_overdue:{slip.id}"
            try:
                try:
                    month_num = datetime.strptime((slip.month or "").strip(), "%B").month
                    year_num = int(slip.year)
                except (ValueError, TypeError):
                    continue
                days_in_month = calendar.monthrange(year_num, month_num)[1]
                period_end = datetime(year_num, month_num, days_in_month)
                if now < period_end + timedelta(days=PAYROLL_FINALIZATION_GRACE_DAYS):
                    continue
                employee_name = slip.employee.name if slip.employee else "An employee"
                days_overdue = (now - period_end).days
                AutomationService._notify_and_log(
                    db, rule_key=AutomationService.RULE_PAYROLL_FINALIZATION_OVERDUE, trigger_event=trigger_event,
                    condition_summary=(
                        f"Salary slip (id={slip.id}) for {employee_name} - {slip.month} {slip.year} - "
                        f"is still 'draft', {days_overdue} day(s) after the pay period ended."
                    ),
                    notification_type="PAYROLL_FINALIZATION_OVERDUE", severity="WARNING",
                    title=f"Payroll not finalized - {employee_name} ({slip.month} {slip.year})",
                    message=(
                        f"{employee_name}'s salary slip for {slip.month} {slip.year} is still in draft, "
                        f"{days_overdue} day(s) after the pay period ended."
                    ),
                    entity_type="salary_slip", entity_id=slip.id, dedup_key=dedup_key,
                    action_taken="notify:PAYROLL_FINALIZATION_OVERDUE", action_path="/salary-slips",
                    recipient_user_id=None,
                )
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=AutomationService.RULE_PAYROLL_FINALIZATION_OVERDUE, trigger_event=trigger_event,
                    condition_summary=f"Failed while evaluating salary slip id={slip.id}.",
                    action_taken="notify:PAYROLL_FINALIZATION_OVERDUE", status="FAILED",
                    entity_type="salary_slip", entity_id=slip.id, dedup_key=dedup_key, error_message=str(exc),
                )

    # ---------------------------------------------------------------- #
    # Rule: Operational summary -> one consolidated broadcast
    # Not a second analytics system: every count here is a direct query
    # against the same tables/conditions the other rules and
    # analytics_service already use (overdue tasks, low/out of stock,
    # blocked production, purchases due soon, follow-ups due, deadlines
    # approaching). dedup_key is date-scoped so this fires at most once
    # per calendar day regardless of how many times the scheduler/panel
    # triggers a check.
    # ---------------------------------------------------------------- #
    @staticmethod
    def check_operational_summary(db: Session, trigger_event: str = "on_demand_check") -> None:
        now = datetime.utcnow()
        today = now.date()
        dedup_key = f"automation:operational_summary:{today.isoformat()}"
        try:
            overdue_tasks = db.query(DailyTask).filter(
                DailyTask.status != "DONE", DailyTask.date.isnot(None), DailyTask.date < now,
            ).count()
            low_stock = db.query(Material).filter(Material.is_active.is_(True)).all()
            low_stock_count = sum(1 for m in low_stock if m.stock_status in ("LOW STOCK", "OUT OF STOCK"))
            blocked_production = db.query(ProductionJob).filter(ProductionJob.status == "Blocked").count()
            window_end = now + timedelta(days=DELIVERY_APPROACHING_WINDOW_DAYS)
            pending_purchases = db.query(Purchase).filter(
                Purchase.receipt_status.in_(["Ordered", "Partially Received"]),
                Purchase.expected_delivery_date.isnot(None), Purchase.expected_delivery_date <= window_end,
            ).count()
            pending_follow_ups = db.query(ClientActivity).filter(
                ClientActivity.follow_up_date.isnot(None), ClientActivity.follow_up_date <= now,
                ClientActivity.follow_up_done.is_(False),
            ).count()
            deadline_window_end = now + timedelta(days=MILESTONE_DEADLINE_APPROACHING_WINDOW_DAYS)
            approaching_deadlines = db.query(Milestone).filter(
                Milestone.completed_date.is_(None), Milestone.target_date.isnot(None),
                Milestone.target_date >= now, Milestone.target_date <= deadline_window_end,
            ).count()

            items = [
                (overdue_tasks, f"{overdue_tasks} task(s) overdue"),
                (approaching_deadlines, f"{approaching_deadlines} project deadline(s) approaching"),
                (blocked_production, f"{blocked_production} production job(s) blocked"),
                (low_stock_count, f"{low_stock_count} material(s) low/out of stock"),
                (pending_purchases, f"{pending_purchases} purchase(s) due soon"),
                (pending_follow_ups, f"{pending_follow_ups} client follow-up(s) due"),
            ]
            active = [text for count, text in items if count > 0]
            if not active:
                message = "No overdue tasks, approaching deadlines, blocked production, low stock, " \
                          "pending purchases, or pending follow-ups right now."
            else:
                message = "Operational summary: " + "; ".join(active) + "."

            AutomationService._notify_and_log(
                db, rule_key=AutomationService.RULE_OPERATIONAL_SUMMARY, trigger_event=trigger_event,
                condition_summary=f"Daily operational summary for {today.isoformat()}.",
                notification_type="OPERATIONAL_SUMMARY", severity="INFO",
                title=f"Operational summary - {today.strftime('%d %b %Y')}",
                message=message, entity_type="operational_summary", entity_id=None, dedup_key=dedup_key,
                action_taken="notify:OPERATIONAL_SUMMARY", action_path="/dashboard",
                recipient_user_id=None,
            )
        except Exception as exc:
            db.rollback()
            AutomationService._log(
                db, rule_key=AutomationService.RULE_OPERATIONAL_SUMMARY, trigger_event=trigger_event,
                condition_summary="Failed while building the operational summary.",
                action_taken="notify:OPERATIONAL_SUMMARY", status="FAILED", error_message=str(exc),
            )

    # ---------------------------------------------------------------- #
    # Orchestration
    # ---------------------------------------------------------------- #
    @staticmethod
    def run_all(db: Session, trigger_event: str = "on_demand_check") -> None:
        """Runs every rule. Each rule already isolates its own per-record
        failures (see the try/except in each check_* above), so one bad
        record never stops the others - here too, one rule raising
        unexpectedly must not stop the rest from running."""
        for check in (
            AutomationService.check_task_overdue,
            AutomationService.check_low_stock_purchase_recommendations,
            AutomationService.check_order_at_risk_material_shortage,
            AutomationService.check_delivery_risk_critical,
            AutomationService.check_purchase_delivery_approaching,
            AutomationService.check_payment_overdue,
            AutomationService.check_project_delayed,
            AutomationService.check_production_blocked,
            AutomationService.check_follow_up_due,
            AutomationService.check_pending_estimate_response,
            AutomationService.check_project_deadline_approaching,
            AutomationService.check_pending_leave_approval,
            AutomationService.check_pending_salary_advance_approval,
            AutomationService.check_payroll_finalization_overdue,
            AutomationService.check_operational_summary,
        ):
            try:
                check(db, trigger_event)
            except Exception as exc:
                db.rollback()
                AutomationService._log(
                    db, rule_key=getattr(check, "__name__", "unknown_rule"), trigger_event=trigger_event,
                    condition_summary="Rule failed at the top level (outside per-record handling).",
                    action_taken="run_rule", status="FAILED", error_message=str(exc),
                )
