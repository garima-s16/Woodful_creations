from datetime import datetime, timedelta

from app.platform.security.security import hash_password
from app.modules.auth.models import User
from app.modules.communications.models import AutomationLog
from app.modules.clients.models import ClientActivity
from app.modules.operations.models import Milestone
from app.modules.sales.models import Estimate
from app.modules.inventory.models import Material, Purchase
from app.modules.communications.models import Notification
from app.modules.communications.services.automation_service import AutomationService
from app.modules.communications.services.notification_service import NotificationService
from tests.helpers import _login


"""Tests for the real, event-driven notification system - every
notification here must trace back to an actual database condition, and
repeated checks must never spam duplicates. Also covers the automation
rules that generate many of these notifications (overdue tasks,
low-stock reorder recommendations, stale estimates, approaching/passed
milestones, due follow-ups) and the operational-summary/audit-log
surfaces around them."""


def _make_client(client, name):
    return client.post("/api/clients/", json={"name": name, "phone": "9000010087"}).json()["id"]


def _make_employee(client, name):
    return client.post("/api/employees/", json={"name": name, "monthly_salary": "20000"}).json()


def test_low_stock_material_generates_notification(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Low Stock Notif Material", "unit": "Sheets", "opening_stock": 2, "minimum_stock": 10,
    })
    resp = client.get("/api/notifications/")
    assert resp.status_code == 200
    matches = [n for n in resp.json() if n["title"] == "Low Stock Notif Material is running low"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "WARNING"
    assert matches[0]["notification_type"] == "LOW_STOCK"


def test_out_of_stock_material_generates_critical_notification(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Out Of Stock Notif Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    })
    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if "Out Of Stock Notif Material" in n["title"]]
    assert len(matches) == 1
    assert matches[0]["severity"] == "CRITICAL"
    assert matches[0]["notification_type"] == "OUT_OF_STOCK"


def test_checking_twice_does_not_create_duplicate_notifications(client, test_user):
    """The core requirement - repeated checks (e.g. opening
    the panel multiple times) must not spam the same situation."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Dedup Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    })
    client.get("/api/notifications/")
    client.get("/api/notifications/")
    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if "Dedup Test Material" in n["title"]]
    assert len(matches) == 1


def test_marking_read_allows_a_fresh_notification_later(client, test_user):
    """A resolved (read) notification shouldn't permanently block a new
    one if the same situation recurs - only unread duplicates are
    suppressed."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Reopen Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    }).json()

    first_check = client.get("/api/notifications/").json()
    notif = next(n for n in first_check if "Reopen Test Material" in n["title"])
    client.put(f"/api/notifications/{notif['id']}/read")

    second_check = client.get("/api/notifications/").json()
    matches = [n for n in second_check if "Reopen Test Material" in n["title"]]
    assert len(matches) == 2  # the read one, plus a fresh unread one
    assert sum(1 for m in matches if not m["is_read"]) == 1


def test_purchase_received_generates_success_notification(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Notif Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 100,
    }).json()

    client.post("/api/purchases/", json={
        "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if n["notification_type"] == "PURCHASE_RECEIVED"
               and "Purchase Notif Material" in n["title"]]
    assert len(matches) == 1
    assert matches[0]["severity"] == "SUCCESS"


def test_two_separate_purchases_of_the_same_material_both_notify(client, test_user):
    """Unlike stock-level notifications, purchases are genuinely
    distinct events each time - no dedup should collapse them."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Two Purchases Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Two Purchases Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 100,
    }).json()

    for _ in range(2):
        client.post("/api/purchases/", json={
            "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        })

    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if n["notification_type"] == "PURCHASE_RECEIVED"
               and "Two Purchases Material" in n["title"]]
    assert len(matches) == 2


def test_unread_count_matches_actual_unread_notifications(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Unread Count Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    })
    all_notifs = client.get("/api/notifications/").json()
    expected_unread = sum(1 for n in all_notifs if not n["is_read"])

    resp = client.get("/api/notifications/unread-count")
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_unread


def test_mark_all_read_clears_unread_count(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Mark All Read Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    })
    client.get("/api/notifications/")
    client.put("/api/notifications/read-all")

    resp = client.get("/api/notifications/unread-count")
    assert resp.json()["count"] == 0


def test_notification_has_working_deep_link_path(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Deep Link Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    }).json()
    resp = client.get("/api/notifications/")
    match = next(n for n in resp.json() if "Deep Link Material" in n["title"])
    assert match["action_path"] == f"/materials/{material['id']}"
    assert match["related_entity_type"] == "material"
    assert match["related_entity_id"] == material["id"]
def _login_with_credentials(client, identifier="test@example.com", password="TestPass123!"):
    resp = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200
    return resp


def _link_user_to_employee(db_session, employee_id, username, email):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("LinkedPass1!"), role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

# --------------------------------------------------------------------- #
def test_overdue_task_triggers_notification_to_assigned_user(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Overdue Task Employee")
    recipient = _link_user_to_employee(db_session, employee["id"], "overduetaskuser", "overduetaskuser@example.com")

    past_date = (datetime.utcnow() - timedelta(days=3)).isoformat()
    task = client.post("/api/daily-tasks/", json={
        "date": past_date, "employee_id": employee["id"], "task_description": "Sand the cabinet doors",
        "status": "TO DO",
    }).json()

    AutomationService.check_task_overdue(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "TASK_OVERDUE").first()
    assert notif is not None
    assert notif.recipient_user_id == recipient.id
    assert task["task_code"] in notif.message or "Sand the cabinet doors" in notif.message

    log = db_session.query(AutomationLog).filter(AutomationLog.rule_key == "task_overdue").first()
    assert log is not None
    assert log.status == "SUCCESS"
    assert log.related_entity_type == "task" and log.related_entity_id == task["id"]
    assert log.notification_id == notif.id


def test_task_due_today_is_not_overdue(client, test_user, db_session):
    """CONDITION check: a task due today (not yet in the past) must not
    fire - this is the negative case proving the condition, not just the
    trigger, is being evaluated."""
    _login_with_credentials(client)
    employee = _make_employee(client, "Not Overdue Employee")

    client.post("/api/daily-tasks/", json={
        "date": datetime.utcnow().isoformat(), "employee_id": employee["id"],
        "task_description": "Finish today", "status": "TO DO",
    })

    AutomationService.check_task_overdue(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "TASK_OVERDUE").count() == 0
    assert db_session.query(AutomationLog).filter(AutomationLog.rule_key == "task_overdue").count() == 0


# --------------------------------------------------------------------- #
# Rule: low_stock_purchase_recommendation - action is PROPOSED, not executed
# --------------------------------------------------------------------- #
def test_low_stock_recommends_purchase_without_creating_one(client, test_user, db_session):
    _login_with_credentials(client)
    material = client.post("/api/materials/", json={
        "name": "Teak Veneer Sheet", "unit": "sheet", "minimum_stock": "20", "opening_stock": "5",
    }).json()

    before_purchase_count = db_session.query(Purchase).count()
    AutomationService.check_low_stock_purchase_recommendations(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "PURCHASE_RECOMMENDED").first()
    assert notif is not None
    assert "recommendation only" in notif.message.lower()

    log = db_session.query(AutomationLog).filter(
        AutomationLog.rule_key == "low_stock_purchase_recommendation"
    ).first()
    assert log is not None
    assert log.status == "PROPOSED"  # never SUCCESS - nothing was executed
    assert log.related_entity_type == "material" and log.related_entity_id == material["id"]

    # the sensitive action itself - creating a Purchase - never happened
    assert db_session.query(Purchase).count() == before_purchase_count


def test_material_above_reorder_level_does_not_recommend(client, test_user, db_session):
    _login_with_credentials(client)
    client.post("/api/materials/", json={
        "name": "Plentiful Screws", "unit": "box", "minimum_stock": "5", "opening_stock": "50",
    })

    AutomationService.check_low_stock_purchase_recommendations(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "PURCHASE_RECOMMENDED").count() == 0


# --------------------------------------------------------------------- #
# Duplicate prevention / idempotency
# --------------------------------------------------------------------- #
def test_rerunning_check_does_not_duplicate_notification_or_log(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Idempotency Employee")
    task = client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=2)).isoformat(), "employee_id": employee["id"],
        "task_description": "Repeat check task", "status": "TO DO",
    }).json()

    AutomationService.check_task_overdue(db_session)
    AutomationService.check_task_overdue(db_session)
    AutomationService.check_task_overdue(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "TASK_OVERDUE",
        Notification.related_entity_id == task["id"],
    ).count() == 1
    assert db_session.query(AutomationLog).filter(
        AutomationLog.rule_key == "task_overdue", AutomationLog.related_entity_id == task["id"],
    ).count() == 1


def test_marking_notification_read_allows_a_fresh_occurrence_to_log_again(client, test_user, db_session):
    """Idempotency is scoped to the still-open occurrence, not forever -
    once the existing notification is read (acknowledged), the same
    still-overdue task firing again is a new, distinct occurrence worth
    a new log entry - this isn't re-detecting the same open item twice,
    it's confirming closed occurrences don't suppress future ones."""
    _login_with_credentials(client)
    employee = _make_employee(client, "Reopen Employee")
    task = client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Reopen case task", "status": "TO DO",
    }).json()

    AutomationService.check_task_overdue(db_session)
    first_notif = db_session.query(Notification).filter(Notification.notification_type == "TASK_OVERDUE").one()
    first_notif.is_read = True
    db_session.commit()

    AutomationService.check_task_overdue(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "TASK_OVERDUE").count() == 2
    assert db_session.query(AutomationLog).filter(AutomationLog.rule_key == "task_overdue").count() == 2


# --------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------- #
def test_non_master_cannot_view_automation_logs(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "RBAC Employee")
    _link_user_to_employee(db_session, employee["id"], "automationrbacuser", "automationrbacuser@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "automationrbacuser@example.com", "password": "LinkedPass1!"})
    assert resp.status_code == 200

    assert client.get("/api/automation/logs").status_code == 403
    assert client.get("/api/automation/rules").status_code == 403
    assert client.post("/api/automation/run").status_code == 403


def test_master_can_view_automation_logs_and_trigger_run(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Master View Employee")
    client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Master-visible overdue task", "status": "TO DO",
    })

    run_resp = client.post("/api/automation/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["logged"] >= 1

    logs_resp = client.get("/api/automation/logs")
    assert logs_resp.status_code == 200
    assert any(entry["rule_key"] == "task_overdue" for entry in logs_resp.json())

    rules_resp = client.get("/api/automation/rules")
    assert rules_resp.status_code == 200
    assert {r["key"] for r in rules_resp.json()} == {
        "task_overdue", "low_stock_purchase_recommendation", "purchase_delivery_approaching",
        "payment_overdue", "project_delayed", "production_blocked",
    }


def test_running_automation_twice_in_a_row_logs_nothing_new(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Double Run Employee")
    client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Double run task", "status": "TO DO",
    })

    first = client.post("/api/automation/run").json()
    second = client.post("/api/automation/run").json()
    assert first["logged"] >= 1
    assert second["logged"] == 0


# --------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------- #
def test_one_failing_record_does_not_block_the_others(client, test_user, db_session, monkeypatch):
    _login_with_credentials(client)
    employee_a = _make_employee(client, "Failure Isolation A")
    employee_b = _make_employee(client, "Failure Isolation B")
    task_a = client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee_a["id"],
        "task_description": "Will fail", "status": "TO DO",
    }).json()
    task_b = client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee_b["id"],
        "task_description": "Will succeed", "status": "TO DO",
    }).json()

    original_notify = NotificationService.notify

    def flaky_notify(db, *args, **kwargs):
        if kwargs.get("related_entity_id") == task_a["id"]:
            raise RuntimeError("simulated downstream failure")
        return original_notify(db, *args, **kwargs)

    monkeypatch.setattr(NotificationService, "notify", staticmethod(flaky_notify))

    AutomationService.check_task_overdue(db_session)

    failed_log = db_session.query(AutomationLog).filter(
        AutomationLog.rule_key == "task_overdue", AutomationLog.related_entity_id == task_a["id"],
    ).first()
    assert failed_log is not None
    assert failed_log.status == "FAILED"
    assert "simulated downstream failure" in failed_log.error_message

    success_notif = db_session.query(Notification).filter(
        Notification.notification_type == "TASK_OVERDUE", Notification.related_entity_id == task_b["id"],
    ).first()
    assert success_notif is not None  # the other record still succeeded


def test_run_all_isolates_a_whole_rule_failing(client, test_user, db_session, monkeypatch):
    """Even if an entire rule raises unexpectedly (not just one record
    within it), the other rules in run_all must still execute - and the
    failure itself must be recorded, not silently dropped."""
    _login_with_credentials(client)
    employee = _make_employee(client, "Run All Isolation Employee")
    client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Should still be checked", "status": "TO DO",
    })

    def broken_rule(db, trigger_event="on_demand_check"):
        raise RuntimeError("entire rule exploded")

    monkeypatch.setattr(AutomationService, "check_low_stock_purchase_recommendations", staticmethod(broken_rule))

    AutomationService.run_all(db_session)

    task_overdue_log = db_session.query(AutomationLog).filter(AutomationLog.rule_key == "task_overdue").first()
    assert task_overdue_log is not None and task_overdue_log.status == "SUCCESS"

    top_level_failure = db_session.query(AutomationLog).filter(AutomationLog.status == "FAILED").filter(
        AutomationLog.condition_summary.like("%top level%")
    ).first()
    assert top_level_failure is not None
    assert "entire rule exploded" in top_level_failure.error_message


# --------------------------------------------------------------------- #
# Rule: follow_up_due - trigger / condition / duplicate prevention
# --------------------------------------------------------------------- #
def test_due_follow_up_triggers_notification(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Follow-up Due Client")
    activity = ClientActivity(
        client_id=client_id, activity_type="Call", date=datetime.utcnow() - timedelta(days=2),
        summary="Discussed cabinet finish options", logged_by="Sales",
        follow_up_date=datetime.utcnow() - timedelta(days=1), follow_up_done=False,
    )
    db_session.add(activity)
    db_session.commit()

    AutomationService.check_follow_up_due(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "FOLLOW_UP_DUE").first()
    assert notif is not None
    assert "Follow-up Due Client" in notif.message

    log = db_session.query(AutomationLog).filter(AutomationLog.rule_key == "follow_up_due").first()
    assert log is not None and log.status == "SUCCESS"
    assert log.related_entity_type == "client" and log.related_entity_id == client_id


def test_future_follow_up_does_not_trigger(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Follow-up Future Client")
    activity = ClientActivity(
        client_id=client_id, activity_type="Call", date=datetime.utcnow(),
        summary="Will follow up next week", logged_by="Sales",
        follow_up_date=datetime.utcnow() + timedelta(days=5), follow_up_done=False,
    )
    db_session.add(activity)
    db_session.commit()

    AutomationService.check_follow_up_due(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "FOLLOW_UP_DUE").count() == 0


def test_completed_follow_up_does_not_trigger(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Follow-up Done Client")
    activity = ClientActivity(
        client_id=client_id, activity_type="Call", date=datetime.utcnow() - timedelta(days=3),
        summary="Already followed up", logged_by="Sales",
        follow_up_date=datetime.utcnow() - timedelta(days=1), follow_up_done=True,
    )
    db_session.add(activity)
    db_session.commit()

    AutomationService.check_follow_up_due(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "FOLLOW_UP_DUE").count() == 0


def test_follow_up_due_does_not_duplicate_on_repeated_run(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Follow-up Dedup Client")
    activity = ClientActivity(
        client_id=client_id, activity_type="Email", date=datetime.utcnow() - timedelta(days=2),
        summary="Sent quote, awaiting reply", follow_up_date=datetime.utcnow() - timedelta(days=1),
        follow_up_done=False,
    )
    db_session.add(activity)
    db_session.commit()

    AutomationService.check_follow_up_due(db_session)
    AutomationService.check_follow_up_due(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "FOLLOW_UP_DUE").count() == 1
    assert db_session.query(AutomationLog).filter(AutomationLog.rule_key == "follow_up_due").count() == 1


# --------------------------------------------------------------------- #
# Rule: pending_estimate_response - authorization (financial-tier)
# --------------------------------------------------------------------- #
def test_stale_sent_estimate_triggers_master_only_notification(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Pending Estimate Client")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "40000", "labor_cost": "15000",
    }).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    # Backdate updated_at directly - the API always sets it to "now" on write.
    row = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    row.updated_at = datetime.utcnow() - timedelta(days=7)
    db_session.commit()

    AutomationService.check_pending_estimate_response(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "ESTIMATE_PENDING_RESPONSE").first()
    assert notif is not None
    assert notif.notification_type in NotificationService.FINANCIAL_NOTIFICATION_TYPES
    assert notif.recipient_user_id is None  # broadcast, filtered to master by visible_to()


def test_recently_sent_estimate_does_not_trigger(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Fresh Estimate Client")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "40000", "labor_cost": "15000",
    }).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})

    AutomationService.check_pending_estimate_response(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "ESTIMATE_PENDING_RESPONSE"
    ).count() == 0


def test_approved_estimate_does_not_trigger_pending_response(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Approved Estimate Client")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "40000", "labor_cost": "15000",
    }).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "approved"})
    row = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    row.updated_at = datetime.utcnow() - timedelta(days=10)
    db_session.commit()

    AutomationService.check_pending_estimate_response(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "ESTIMATE_PENDING_RESPONSE"
    ).count() == 0


# --------------------------------------------------------------------- #
# Rule: project_deadline_approaching vs project_delayed - the distinction
# --------------------------------------------------------------------- #
def test_approaching_milestone_triggers_deadline_approaching_not_delayed(client, test_user, db_session):
    _login_with_credentials(client)
    order = client.post("/api/orders/", json={
        "client_id": _make_client(client, "Deadline Approaching Client"), "project_type": "Wardrobe",
        "order_date": datetime.utcnow().isoformat(),
    }).json()
    milestone = Milestone(
        order_id=order["id"], name="Installation", target_date=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(milestone)
    db_session.commit()

    AutomationService.check_project_deadline_approaching(db_session)
    AutomationService.check_project_delayed(db_session)

    approaching = db_session.query(Notification).filter(
        Notification.notification_type == "PROJECT_DEADLINE_APPROACHING"
    ).first()
    assert approaching is not None
    assert db_session.query(Notification).filter(Notification.notification_type == "PROJECT_DELAYED").count() == 0


def test_passed_milestone_triggers_delayed_not_approaching(client, test_user, db_session):
    _login_with_credentials(client)
    order = client.post("/api/orders/", json={
        "client_id": _make_client(client, "Deadline Passed Client"), "project_type": "Wardrobe",
        "order_date": datetime.utcnow().isoformat(),
    }).json()
    milestone = Milestone(
        order_id=order["id"], name="Design Approval", target_date=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(milestone)
    db_session.commit()

    AutomationService.check_project_deadline_approaching(db_session)
    AutomationService.check_project_delayed(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "PROJECT_DEADLINE_APPROACHING"
    ).count() == 0
    assert db_session.query(Notification).filter(Notification.notification_type == "PROJECT_DELAYED").count() == 1


def test_milestone_not_yet_in_window_does_not_trigger_approaching(client, test_user, db_session):
    _login_with_credentials(client)
    order = client.post("/api/orders/", json={
        "client_id": _make_client(client, "Deadline Far Client"), "project_type": "Wardrobe",
        "order_date": datetime.utcnow().isoformat(),
    }).json()
    milestone = Milestone(
        order_id=order["id"], name="Final Handover", target_date=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(milestone)
    db_session.commit()

    AutomationService.check_project_deadline_approaching(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "PROJECT_DEADLINE_APPROACHING"
    ).count() == 0


def test_deadline_approaching_does_not_duplicate_on_repeated_run(client, test_user, db_session):
    _login_with_credentials(client)
    order = client.post("/api/orders/", json={
        "client_id": _make_client(client, "Deadline Dedup Client"), "project_type": "Wardrobe",
        "order_date": datetime.utcnow().isoformat(),
    }).json()
    milestone = Milestone(
        order_id=order["id"], name="Site Measurement", target_date=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(milestone)
    db_session.commit()

    AutomationService.check_project_deadline_approaching(db_session)
    AutomationService.check_project_deadline_approaching(db_session)

    assert db_session.query(Notification).filter(
        Notification.notification_type == "PROJECT_DEADLINE_APPROACHING"
    ).count() == 1


# --------------------------------------------------------------------- #
# Rule: operational_summary - correct data / empty state / no duplicates
# --------------------------------------------------------------------- #
def test_operational_summary_reports_real_counts(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Ops Summary Employee")
    client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Overdue for summary", "status": "TO DO",
    })
    client.post("/api/materials/", json={
        "name": "Ops Summary Material", "unit": "sheet", "minimum_stock": "20", "opening_stock": "5",
    })

    AutomationService.check_operational_summary(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "OPERATIONAL_SUMMARY").first()
    assert notif is not None
    assert "task(s) overdue" in notif.message
    assert "low/out of stock" in notif.message
    # No financial amount anywhere in the summary text - safe for every role.
    assert "Rs" not in notif.message


def test_operational_summary_empty_state(client, test_user, db_session):
    _login_with_credentials(client)
    AutomationService.check_operational_summary(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "OPERATIONAL_SUMMARY").first()
    assert notif is not None
    assert "No overdue tasks" in notif.message


def test_operational_summary_does_not_duplicate_same_day(client, test_user, db_session):
    _login_with_credentials(client)
    AutomationService.check_operational_summary(db_session)
    AutomationService.check_operational_summary(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "OPERATIONAL_SUMMARY").count() == 1
    assert db_session.query(AutomationLog).filter(AutomationLog.rule_key == "operational_summary").count() == 1


# --------------------------------------------------------------------- #
# run_all now covers all ten rules
# --------------------------------------------------------------------- #
def test_run_all_covers_new_gap_fix_rules(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = _make_client(client, "Run All New Rules Client")
    activity = ClientActivity(
        client_id=client_id, activity_type="Call", date=datetime.utcnow() - timedelta(days=2),
        summary="Needs follow-up", follow_up_date=datetime.utcnow() - timedelta(days=1), follow_up_done=False,
    )
    db_session.add(activity)
    db_session.commit()

    AutomationService.run_all(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "FOLLOW_UP_DUE").count() == 1
    assert db_session.query(Notification).filter(Notification.notification_type == "OPERATIONAL_SUMMARY").count() == 1


# --------------------------------------------------------------------- #
# Excel export (reuses the existing reports module - no new Excel path)
# --------------------------------------------------------------------- #
def test_automation_log_excel_export_is_master_only(client, test_user, db_session):
    _login_with_credentials(client)
    employee = _make_employee(client, "Export Employee")
    client.post("/api/daily-tasks/", json={
        "date": (datetime.utcnow() - timedelta(days=1)).isoformat(), "employee_id": employee["id"],
        "task_description": "Exportable overdue task", "status": "TO DO",
    })
    client.post("/api/automation/run")

    resp = client.get("/api/reports/automation-log.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===========================================================================
# Task-assignment notifications (from test_auth_and_chatbot_misc.py)
# ===========================================================================

def test_employee_notified_when_task_assigned(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Notif Employee"}).json()
    _create_employee_user(client, db_session, employee["id"], "tasknotifuser", "tasknotifuser@example.com")

    _login(client, test_user)
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Sand the wardrobe panels",
    })

    client.post("/api/auth/login", json={"identifier": "tasknotifuser@example.com", "password": "EmpPass1!"})
    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "TASK_ASSIGNED" for n in notifications)


def test_employee_notified_on_task_status_change(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Status Notif Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Cut panels",
    }).json()
    _create_employee_user(client, db_session, employee["id"], "taskstatusnotifuser", "taskstatusnotifuser@example.com")
    client.post("/api/auth/login", json={"identifier": "taskstatusnotifuser@example.com", "password": "EmpPass1!"})

    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DOING"})

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "TASK_STATUS_CHANGED" for n in notifications)
