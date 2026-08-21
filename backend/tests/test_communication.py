"""Family 11 - communication & notifications.

Focused tests for the pieces that didn't already have coverage
elsewhere: the /api/communication/* endpoints (search, insights,
draft), @mention notification delivery, and read/unread notification
authorization. Cross-client/cross-project *record* isolation and
attachment authorization are already covered by the existing
per-family test files (task/order/client reads are intentionally not
role-gated in this app - see PROJECT_DOCUMENTATION.md - so the
isolation that matters here is the financial-content masking these
tests exercise instead).

Employee/client/order creation all require master (require_role in
their routes), so every helper here creates its fixtures while logged
in as master and only switches the session to an employee right
before the assertion that needs that employee's point of view.
"""
from datetime import datetime, timedelta

from app.core.security import hash_password
from app.models.user import User
from app.models.order import Order


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


# --------------------------------------------------------------------- #
# communication search authorization
# --------------------------------------------------------------------- #
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


# --------------------------------------------------------------------- #
# mentions
# --------------------------------------------------------------------- #
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


# --------------------------------------------------------------------- #
# read/unread authorization
# --------------------------------------------------------------------- #
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


# --------------------------------------------------------------------- #
# AI action authorization (insights/draft) - never a real LLM, never
# sends anything, but the payment-reminder draft purpose is gated the
# same as other financial content in this app.
# --------------------------------------------------------------------- #
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
