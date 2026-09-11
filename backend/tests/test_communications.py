"""Communications domain tests: channels and notifications.
Combines test_communication.py and test_notifications.py."""
from datetime import datetime, timedelta
from app.platform.security import hash_password
from app.modules.auth.auth import User
from app.modules.sales.models import Order
import smtplib
import socket
from unittest.mock import patch, MagicMock
from app.modules.communications.services import EmailService
from app.modules.communications.models import AutomationLog
from app.modules.clients.models import ClientActivity
from app.modules.operations.models import Milestone
from app.modules.sales.models import Estimate
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.communications.models import Notification
from app.modules.communications.automation import AutomationService
from app.modules.communications.services import NotificationService
from tests.helpers import _login


# --- test_communication.py ---
"""Communication & notifications.

Focused tests for the pieces that didn't already have coverage
elsewhere: the /api/communication/* endpoints (search, insights,
draft), @mention notification delivery, and read/unread notification
authorization. Cross-client/cross-project *record* isolation and
attachment authorization are already covered by the existing
domain test files (task/order/client reads are intentionally not
role-gated in this app - see docs/ARCHITECTURE.md's "Key behaviors to know" - so the
isolation that matters here is the financial-content masking these
tests exercise instead).

Employee/client/order creation all require master (require_role in
their routes), so every helper here creates its fixtures while logged
in as master and only switches the session to an employee right
before the assertion that needs that employee's point of view.
"""


def _login(client, identifier="test@example.com", password="TestPass123!"):
    resp = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200


def _create_employee_user(client, db_session, username, email):
    """Must be called while the current session is master (employee
    creation is master-only). Leaves the session logged in as master
    afterward - call _login(client, email, "EmpPass1!") explicitly
    when the test needs that employee's point of view."""
    employee = client.post("/api/employees/", json={
        "name": username, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _login(client)  # back to master, since employee creation required it anyway
    return user


def _make_order(client, client_name="Comm Test Client"):
    """Must be called while the current session is master."""
    client_id = client.post("/api/clients/", json={"name": client_name, "phone": "9000010052"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()
    return client_id, order


def _backdate_order_for_overdue(db_session, order_id):
    db_order = db_session.query(Order).filter(Order.id == order_id).first()
    db_order.order_date = datetime.utcnow() - timedelta(days=45)
    db_session.add(db_order)
    db_session.commit()


def test_search_surfaces_order_comment_matching_keyword(client, test_user):
    _login(client)
    _, order = _make_order(client)
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "Discussed the payment schedule with client"})

    results = client.get("/api/communication/search", params={"q": "payment"}).json()
    assert any(r["type"] == "order_comment" and "payment" in r["snippet"].lower() for r in results)


def test_search_hides_master_only_financial_notification_from_employee(client, test_user, db_session):
    """The exact case called out in the brief: an employee searching
    'payment'-adjacent terms must not receive the master-only
    PAYMENT_OVERDUE notification content, even though it matches."""
    _login(client)
    _, order = _make_order(client, "Comm Overdue Client")
    _backdate_order_for_overdue(db_session, order["id"])
    client.get("/api/notifications/")  # triggers on-demand notification generation

    _create_employee_user(client, db_session, "commsearchuser", "commsearchuser@example.com")
    _login(client, "commsearchuser@example.com", "EmpPass1!")
    results = client.get("/api/communication/search", params={"q": "overdue"}).json()
    assert not any(r["type"] == "notification" for r in results)


def test_search_shows_financial_notification_to_master(client, test_user, db_session):
    _login(client)
    _, order = _make_order(client, "Comm Overdue Master Client")
    _backdate_order_for_overdue(db_session, order["id"])
    client.get("/api/notifications/")

    results = client.get("/api/communication/search", params={"q": "overdue"}).json()
    assert any(r["type"] == "notification" for r in results)


def test_mention_in_task_comment_notifies_mentioned_user(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "priya", "priya@example.com")
    employee = client.post("/api/employees/", json={
        "name": "task-author-emp", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-01T00:00:00", "employee_id": employee["id"], "task_description": "Cut panels",
    }).json()
    client.post(f"/api/daily-tasks/{task['id']}/comments", json={"text": "@priya can you check this before Friday"})

    _login(client, "priya@example.com", "EmpPass1!")
    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "MENTION" and "task" in n["title"].lower() for n in notifications)


def test_mention_in_order_comment_notifies_mentioned_user_only(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "arjun", "arjun@example.com")
    _create_employee_user(client, db_session, "kavya", "kavya@example.com")
    _, order = _make_order(client, "Mention Order Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@arjun please review the design"})

    _login(client, "arjun@example.com", "EmpPass1!")
    arjun_notifs = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "MENTION" for n in arjun_notifs)

    _login(client, "kavya@example.com", "EmpPass1!")
    kavya_notifs = client.get("/api/notifications/").json()
    assert not any(n["notification_type"] == "MENTION" for n in kavya_notifs)


def test_self_mention_does_not_notify_the_author(client, test_user, db_session):
    """excluded_user_id must suppress a mention of your own account -
    e.g. quoting your own username in a reply thread."""
    _login(client)
    _create_employee_user(client, db_session, "selfauthor", "selfauthor@example.com")
    _, order = _make_order(client, "Self Mention Client")  # as master

    _login(client, "selfauthor@example.com", "EmpPass1!")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@selfauthor noting this for myself"})

    notifications = client.get("/api/notifications/").json()
    assert not any(n["notification_type"] == "MENTION" for n in notifications)


def test_mention_of_unknown_username_does_not_error(client, test_user):
    _login(client)
    _, order = _make_order(client, "Unknown Mention Client")
    resp = client.post(f"/api/orders/{order['id']}/comments", json={"text": "@nobody-such-user please look"})
    assert resp.status_code == 201


def test_mention_creates_exactly_one_notification_per_comment(client, test_user, db_session):
    """dedup_key is keyed on the specific comment+user, so a single
    mention in a single comment must never fan out into more than one
    notification, even across repeated panel opens (which re-run the
    on-demand notification checks for other notification types)."""
    _login(client)
    _create_employee_user(client, db_session, "dedupuser", "dedupuser@example.com")
    _, order = _make_order(client, "Dedup Mention Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@dedupuser take a look"})

    _login(client, "dedupuser@example.com", "EmpPass1!")
    client.get("/api/notifications/")
    notifications = client.get("/api/notifications/").json()
    mention_count = sum(1 for n in notifications if n["notification_type"] == "MENTION")
    assert mention_count == 1


def test_user_cannot_mark_another_users_addressed_notification_read(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "readtarget", "readtarget@example.com")
    _create_employee_user(client, db_session, "readbystander", "readbystander@example.com")
    _, order = _make_order(client, "Read Auth Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@readtarget please confirm"})

    _login(client, "readtarget@example.com", "EmpPass1!")
    notif_id = next(n["id"] for n in client.get("/api/notifications/").json()
                     if n["notification_type"] == "MENTION")

    _login(client, "readbystander@example.com", "EmpPass1!")
    resp = client.put(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 403


def test_owner_can_mark_own_addressed_notification_read(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "readowner", "readowner@example.com")
    _, order = _make_order(client, "Read Owner Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@readowner please confirm"})

    _login(client, "readowner@example.com", "EmpPass1!")
    notif_id = next(n["id"] for n in client.get("/api/notifications/").json()
                     if n["notification_type"] == "MENTION")
    resp = client.put(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


def test_employee_cannot_mark_financial_broadcast_notification_read(client, test_user, db_session):
    """Regression test (defect repair pass): mark_read used to check
    only `recipient_user_id in (None, my_id)`, which treats EVERY
    broadcast notification (recipient_user_id is None) as visible to
    any authenticated user - including a master-only financial
    broadcast like PAYMENT_OVERDUE. That let a non-master employee
    both mark it read AND receive its title/message (financial
    content) back in the response body, the same leak
    test_search_hides_master_only_financial_notification_from_employee
    guards against for search. mark_read must use the same
    NotificationService.visible_to() rule as every other notification
    endpoint in this router."""
    _login(client)
    _, order = _make_order(client, "Read Auth Financial Client")
    _backdate_order_for_overdue(db_session, order["id"])
    client.get("/api/notifications/")  # triggers on-demand notification generation
    notif_id = next(n["id"] for n in client.get("/api/notifications/").json()
                     if n["notification_type"] == "PAYMENT_OVERDUE")

    _create_employee_user(client, db_session, "financialreadbystander", "financialreadbystander@example.com")
    _login(client, "financialreadbystander@example.com", "EmpPass1!")
    resp = client.put(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 403
    assert "overdue" not in resp.text.lower() and "payment" not in resp.text.lower()


def test_mark_all_read_does_not_touch_notifications_addressed_to_others(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "markalltarget", "markalltarget@example.com")
    _create_employee_user(client, db_session, "markallbystander", "markallbystander@example.com")
    _, order = _make_order(client, "Mark All Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "@markalltarget please confirm"})

    _login(client, "markallbystander@example.com", "EmpPass1!")
    client.put("/api/notifications/read-all")

    _login(client, "markalltarget@example.com", "EmpPass1!")
    notifications = client.get("/api/notifications/").json()
    mention = next(n for n in notifications if n["notification_type"] == "MENTION")
    assert mention["is_read"] is False


def test_payment_reminder_draft_requires_master(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "draftuser", "draftuser@example.com")
    _, order = _make_order(client, "Draft Auth Client")

    _login(client, "draftuser@example.com", "EmpPass1!")
    resp = client.post("/api/communication/draft", json={
        "entity_type": "order", "entity_id": order["id"], "purpose": "payment_reminder",
    })
    assert resp.status_code == 403


def test_follow_up_draft_allowed_for_employee(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "drafteduser2", "drafteduser2@example.com")
    _, order = _make_order(client, "Draft Followup Client")

    _login(client, "drafteduser2@example.com", "EmpPass1!")
    resp = client.post("/api/communication/draft", json={
        "entity_type": "order", "entity_id": order["id"], "purpose": "follow_up",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "template"
    assert "review and send it yourself" in body["note"].lower()


def test_draft_never_actually_sends_anything(client, test_user):
    """There is no send path at all for this endpoint - the response
    is a template string only, confirming AI never dispatches external
    communication on its own."""
    _login(client)
    _, order = _make_order(client, "No Send Client")
    resp = client.post("/api/communication/draft", json={
        "entity_type": "order", "entity_id": order["id"], "purpose": "status_update",
    })
    assert resp.status_code == 200
    assert "draft" in resp.json()
    assert "note" in resp.json()


def test_insights_for_unknown_order_returns_404(client, test_user):
    _login(client)
    resp = client.post("/api/communication/insights", json={"entity_type": "order", "entity_id": 999999})
    assert resp.status_code == 404


def test_insights_rejects_unknown_entity_type(client, test_user):
    _login(client)
    resp = client.post("/api/communication/insights", json={"entity_type": "material", "entity_id": 1})
    assert resp.status_code == 400


def test_insights_summarizes_real_recorded_comments_only(client, test_user):
    """The AI summary must be an extractive summary of what was
    actually recorded, not fabricated - entry_count should match the
    number of comments actually created."""
    _login(client)
    _, order = _make_order(client, "Insights Client")
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "Client requested a design change"})
    client.post(f"/api/orders/{order['id']}/comments", json={"text": "Still waiting to hear back from client"})

    resp = client.post("/api/communication/insights", json={"entity_type": "order", "entity_id": order["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "rule_based_extractive"
    assert body["entry_count"] == 2


def test_client_activity_accepts_follow_up_date(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Follow Up Field Test Client", "phone": "9000010111"}).json()["id"]
    resp = client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-19T00:00:00",
        "summary": "Discussed pricing", "follow_up_date": "2026-08-25T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["follow_up_date"] is not None


def test_email_status_requires_master(client, test_user, db_session):
    _login(client)
    resp = client.get("/api/communication/email-status")
    assert resp.status_code == 200
    body = resp.json()
    assert "sender_email" in body and "is_configured" in body
    # Explicit security requirement: never expose the credential value,
    # even to a Master, through a normal API response.
    assert "password" not in str(body).lower() and "sender_password" not in body

    _create_employee_user(client, db_session, "emailstatususer", "emailstatususer@example.com")
    _login(client, "emailstatususer@example.com", "EmpPass1!")
    assert client.get("/api/communication/email-status").status_code == 403


def test_email_test_requires_master(client, test_user, db_session):
    _login(client)
    _create_employee_user(client, db_session, "emailtestuser", "emailtestuser@example.com")
    _login(client, "emailtestuser@example.com", "EmpPass1!")
    resp = client.post("/api/communication/email-test", json={"recipient_email": "someone@example.com"})
    assert resp.status_code == 403


def test_email_test_uses_the_real_email_service(client, test_user, monkeypatch):
    """A successful test must genuinely prove the configured sender can
    deliver mail through the same EmailService every business email
    uses - not a separate, disconnected check."""
    from app.modules.communications.services import EmailService

    captured = {}

    def fake_send_email(self, to_email, subject, body, **kwargs):
        captured["to_email"] = to_email
        captured["sender_used"] = self.sender_email
        return True
    monkeypatch.setattr(EmailService, "send_email", fake_send_email)

    _login(client)
    resp = client.post("/api/communication/email-test", json={"recipient_email": "recipient@example.com"})
    assert resp.status_code == 200
    assert resp.json()["sent"] is True
    assert captured["to_email"] == "recipient@example.com"


def test_order_send_email_ignores_arbitrary_from_field(client, test_user, monkeypatch):
    """Section 1 - the frontend must never be able to override the
    central Woodful sender identity. An extra "from" field in the
    request body must be silently ignored (Pydantic's default
    extra-field behavior already achieves this - this test proves it,
    rather than assuming it), and the actual sender used must remain
    whatever the backend's own configuration says, never a value
    supplied by the caller."""
    from app.modules.communications.services import EmailService

    captured = {}

    def fake_send_email(self, to_email, subject, body, **kwargs):
        captured["sender_used"] = self.sender_email
        return True
    monkeypatch.setattr(EmailService, "send_email", fake_send_email)

    _login(client)
    c = client.post("/api/clients/", json={"name": "Spoof Test Client", "phone": "9000013000"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-08-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()

    resp = client.post(f"/api/orders/{order['id']}/send-email", params={"kind": "invoice"}, json={
        "recipient_email": "customer@example.com", "subject": "Invoice", "body": "See attached.",
        "from": "attacker@evil.com",  # must be silently ignored, never reach send_email as the sender
    })
    assert resp.status_code == 200
    # send_email's own signature has no sender parameter at all - the
    # sender is always self.sender_email, set from backend config,
    # never anything the caller supplied.
    assert captured["sender_used"] != "attacker@evil.com"


"""EmailService.send_email error categorization (production-readiness
fix, issue 2). Previously the real exception was logged server-side
then discarded - callers only ever saw a plain False, and the API
surfaced a generic "misconfigured" message regardless of the actual
cause. These tests verify each real SMTP/config failure mode is now
categorized correctly via self.last_error, without ever needing a
real mail server - smtplib is mocked directly to raise the exact
exception types a real server would."""


def _service_with_config(monkeypatch, email="woodful@example.com", password="app-password-value"):
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_EMAIL", email)
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_PASSWORD", password)
    monkeypatch.setattr("app.modules.communications.services.settings.SMTP_SERVER", "smtp.gmail.com")
    monkeypatch.setattr("app.modules.communications.services.settings.SMTP_PORT", 587)
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_NAME", "Woodful Creations")
    return EmailService()


def test_missing_sender_credentials_categorized_correctly(monkeypatch):
    service = _service_with_config(monkeypatch, email="", password="")
    sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is False
    assert service.last_error == "missing_configuration"


def test_missing_smtp_server_categorized_correctly(monkeypatch):
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_EMAIL", "woodful@example.com")
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_PASSWORD", "app-password-value")
    monkeypatch.setattr("app.modules.communications.services.settings.SMTP_SERVER", "")
    monkeypatch.setattr("app.modules.communications.services.settings.SMTP_PORT", 587)
    monkeypatch.setattr("app.modules.communications.services.settings.SENDER_NAME", "Woodful Creations")
    service = EmailService()
    sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is False
    assert service.last_error == "missing_configuration"


def test_smtp_authentication_error_categorized_correctly(monkeypatch):
    """The real, common Gmail failure mode - a regular account
    password instead of an app password, or 2FA without an app
    password configured, both surface as SMTPAuthenticationError."""
    service = _service_with_config(monkeypatch)
    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is False
    assert service.last_error == "authentication_failed"


def test_smtp_connection_error_categorized_correctly(monkeypatch):
    """A blocked port, wrong server address, or firewall issue."""
    service = _service_with_config(monkeypatch)
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Cannot connect")):
        sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is False
    assert service.last_error == "connection_failed"


def test_smtp_timeout_categorized_as_connection_failure(monkeypatch):
    """No timeout previously existed at all - a hung connection would
    never resolve. Now bounded, and a timeout is a real, distinct,
    reportable failure rather than an indefinite hang."""
    service = _service_with_config(monkeypatch)
    with patch("smtplib.SMTP", side_effect=socket.timeout("timed out")):
        sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is False
    assert service.last_error == "connection_failed"


def test_successful_send_clears_last_error(monkeypatch):
    service = _service_with_config(monkeypatch)
    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        sent = service.send_email("client@example.com", "Subject", "Body")
    assert sent is True
    assert service.last_error is None
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("woodful@example.com", "app-password-value")


def test_password_value_never_appears_in_last_error_or_logs(monkeypatch, caplog):
    """Explicit security requirement - never expose the actual
    credential value, even in a failure path."""
    service = _service_with_config(monkeypatch, password="super-secret-app-password-xyz")
    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        service.send_email("client@example.com", "Subject", "Body")
    assert "super-secret-app-password-xyz" not in (service.last_error or "")
    assert "super-secret-app-password-xyz" not in caplog.text


def test_attachment_included_when_provided(monkeypatch):
    service = _service_with_config(monkeypatch)
    mock_server = MagicMock()
    sent_messages = []
    mock_server.send_message.side_effect = lambda msg: sent_messages.append(msg)
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        sent = service.send_email(
            "client@example.com", "Invoice", "Please find attached.",
            attachment_bytes=b"%PDF-1.4 fake pdf bytes", attachment_filename="Invoice-WC-2026-001.pdf",
        )
    assert sent is True
    assert len(sent_messages) == 1
    attachment_names = [part.get_filename() for part in sent_messages[0].walk() if part.get_filename()]
    assert "Invoice-WC-2026-001.pdf" in attachment_names


# --- test_notifications.py ---
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


def test_order_at_risk_material_shortage_notifies_with_order_context(client, test_user, db_session):
    """Family 130 - distinct from check_low_stock_purchase_recommendations
    above: that rule only knows a material is low, never which order it
    threatens. This rule must name the actual order."""
    _login_with_credentials(client)
    material = client.post("/api/materials/", json={
        "name": "Automation At Risk Sheet", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Automation At Risk Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Automation At Risk Client", "phone": "9000010600"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    AutomationService.check_order_at_risk_material_shortage(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "ORDER_AT_RISK").first()
    assert notif is not None
    assert "Automation At Risk Sheet" in notif.message
    assert notif.related_entity_type == "order" and notif.related_entity_id == order["id"]

    log = db_session.query(AutomationLog).filter(
        AutomationLog.rule_key == "order_at_risk_material_shortage"
    ).first()
    assert log is not None
    assert log.related_entity_type == "order" and log.related_entity_id == order["id"]


def test_delivery_risk_critical_notifies_with_order_context(client, test_user, db_session):
    """P0.50 section 38 - fires only for the most severe (CRITICAL)
    delivery risk level, reusing OrderService.bulk_attention_flags
    exactly, the same calculation already backing the Orders List and
    Dashboard."""
    from datetime import datetime, timedelta
    _login_with_credentials(client)
    client_id = client.post("/api/clients/", json={"name": "Automation Critical Client", "phone": "9000010650"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Automation Critical Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Automation critical work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    AutomationService.check_delivery_risk_critical(db_session)

    notif = db_session.query(Notification).filter(Notification.notification_type == "DELIVERY_RISK_CRITICAL").first()
    assert notif is not None
    assert notif.severity == "CRITICAL"
    assert notif.related_entity_type == "order" and notif.related_entity_id == order["id"]

    log = db_session.query(AutomationLog).filter(AutomationLog.rule_key == "delivery_risk_critical").first()
    assert log is not None
    assert log.related_entity_id == order["id"]


def test_delivery_risk_critical_does_not_fire_for_on_track_order(client, test_user, db_session):
    _login_with_credentials(client)
    client_id = client.post("/api/clients/", json={"name": "Automation On Track Client", "phone": "9000010651"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
    })

    AutomationService.check_delivery_risk_critical(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "DELIVERY_RISK_CRITICAL").count() == 0


def test_order_with_sufficient_stock_does_not_trigger_at_risk_notification(client, test_user, db_session):
    _login_with_credentials(client)
    material = client.post("/api/materials/", json={
        "name": "Automation No Risk Sheet", "unit": "Sheets", "opening_stock": "100", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Automation No Risk Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "2"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Automation No Risk Client", "phone": "9000010601"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    })

    AutomationService.check_order_at_risk_material_shortage(db_session)

    assert db_session.query(Notification).filter(Notification.notification_type == "ORDER_AT_RISK").count() == 0


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
        "task_overdue", "low_stock_purchase_recommendation", "order_at_risk_material_shortage",
        "delivery_risk_critical",
        "purchase_delivery_approaching", "payment_overdue", "project_delayed", "production_blocked",
        "follow_up_due", "pending_estimate_response", "project_deadline_approaching", "operational_summary",
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


def test_notifications_endpoint_skips_automation_engine_when_scheduler_enabled(client, test_user, db_session, monkeypatch):
    """Production-readiness review fix: with the background scheduler
    enabled, GET /api/notifications/ must not independently re-run the
    entire automation engine on every call - that would mean every
    panel open and every unread-count poll, across every logged-in
    user, duplicates what the scheduler is already doing on its own
    interval."""
    from app.platform import config as config_module
    monkeypatch.setattr(config_module.settings, "AUTOMATION_SCHEDULER_ENABLED", True)
    _login_with_credentials(client)
    client.post("/api/materials/", json={
        "name": "Scheduler Skip Material", "unit": "box", "minimum_stock": "5", "opening_stock": "1",
    })

    client.get("/api/notifications/")

    # The low-stock automation rule was never triggered, because the
    # on-demand fallback correctly stayed off while the scheduler is
    # enabled.
    assert db_session.query(Notification).filter(
        Notification.notification_type == "PURCHASE_RECOMMENDED"
    ).count() == 0


def test_notifications_endpoint_runs_automation_engine_when_scheduler_disabled(client, test_user, db_session, monkeypatch):
    """The complementary case - with the scheduler disabled (this
    fixture's default, and the only way tests can exercise this
    endpoint's fallback), the on-demand check must still run."""
    from app.platform import config as config_module
    monkeypatch.setattr(config_module.settings, "AUTOMATION_SCHEDULER_ENABLED", False)
    _login_with_credentials(client)
    client.post("/api/materials/", json={
        "name": "Scheduler Run Material", "unit": "box", "minimum_stock": "5", "opening_stock": "1",
    })

    client.get("/api/notifications/")

    assert db_session.query(Notification).filter(
        Notification.notification_type == "PURCHASE_RECOMMENDED"
    ).count() >= 1
