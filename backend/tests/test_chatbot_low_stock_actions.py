"""Tests for the low-stock and out-of-stock chat results' action
buttons - master gets a genuine second action (Purchase History),
employees only get the one action they're actually permitted to
reach, since offering a dead-end restricted link isn't a real,
useful business action."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_gets_purchase_history_action_on_low_stock(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Low Stock Actions Master Material", "unit": "Sheets",
        "opening_stock": "1", "minimum_stock": "10",
    })

    resp = client.post("/api/chat/", json={"message": "show me low stock"})
    match = next((r for r in resp.json()["records"] if r["label"] == "Low Stock Actions Master Material"), None)
    assert match is not None
    action_labels = [a["label"] for a in match["actions"]]
    assert "View Purchase History" in action_labels


def test_employee_does_not_get_restricted_action_on_low_stock(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Low Stock Actions Employee Material", "unit": "Sheets",
        "opening_stock": "1", "minimum_stock": "10",
    })
    employee = client.post("/api/employees/", json={"name": "Low Stock Actions Employee"}).json()
    user = User(
        username="lowstockactionsuser", email="lowstockactionsuser@example.com", full_name="Low Stock Actions User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "lowstockactionsuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "show me low stock"})
    match = next((r for r in resp.json()["records"] if r["label"] == "Low Stock Actions Employee Material"), None)
    assert match is not None
    action_labels = [a["label"] for a in match["actions"]]
    assert "View Purchase History" not in action_labels
    assert "View Material" in action_labels


def test_master_gets_purchase_history_action_on_out_of_stock(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Out Of Stock Actions Master Material", "unit": "Sheets",
        "opening_stock": "0", "minimum_stock": "10",
    })

    resp = client.post("/api/chat/", json={"message": "what is out of stock"})
    match = next((r for r in resp.json()["records"] if r["label"] == "Out Of Stock Actions Master Material"), None)
    assert match is not None
    action_labels = [a["label"] for a in match["actions"]]
    assert "View Purchase History" in action_labels


def test_employee_does_not_get_restricted_action_on_out_of_stock(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Out Of Stock Actions Employee Material", "unit": "Sheets",
        "opening_stock": "0", "minimum_stock": "10",
    })
    employee = client.post("/api/employees/", json={"name": "Out Of Stock Actions Employee"}).json()
    user = User(
        username="outofstockactionsuser", email="outofstockactionsuser@example.com", full_name="Out Of Stock Actions User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "outofstockactionsuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "what is out of stock"})
    match = next((r for r in resp.json()["records"] if r["label"] == "Out Of Stock Actions Employee Material"), None)
    assert match is not None
    action_labels = [a["label"] for a in match["actions"]]
    assert "View Purchase History" not in action_labels
    assert "View Material" in action_labels
