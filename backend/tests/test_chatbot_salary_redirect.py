"""Tests confirming the chatbot never returns salary data or figures
for any role - it always redirects to the Salary section, with no
distinction between "my salary" and a named person's salary, and no
distinction between master and employee roles."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client, db_session, name, username, email):
    employee = client.post("/api/employees/", json={"name": name, "monthly_salary": "20000"}).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200
    return employee


def test_employee_asking_for_own_salary_gets_redirect_not_data(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "Chat Salary Redirect Employee", "chatsalaryredirectuser", "chatsalaryredirectuser@example.com")

    resp = client.post("/api/chat/", json={"message": "Show my salary slip"})
    text = resp.json()["response"]
    assert "salary section" in text.lower()
    assert "15,000" not in text
    assert resp.json()["records"][0]["path"] == "/salary-slips"


def test_employee_asking_for_named_persons_salary_gets_same_redirect(client, test_user, db_session):
    """No distinction between own and someone else's salary - both
    produce the identical redirect, matching the simplified design."""
    _login(client, test_user)
    _create_employee(client, db_session, "Chat Salary Redirect Requester", "chatsalaryredirectuser2", "chatsalaryredirectuser2@example.com")

    resp = client.post("/api/chat/", json={"message": "Show Pankaj's salary slip"})
    text = resp.json()["response"]
    assert "salary section" in text.lower()
    assert "don't have access" not in text.lower()


def test_master_asking_for_salary_gets_same_redirect_not_data(client, test_user):
    """Master also never gets salary data through chat - the redirect
    is uniform across roles, not master-privileged data access."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "What is the salary of Ravi?"})
    text = resp.json()["response"]
    assert "salary section" in text.lower()


def test_own_and_named_salary_queries_produce_identical_response_text(client, test_user):
    """The core requirement - no branching by ownership or role at all."""
    _login(client, test_user)
    resp1 = client.post("/api/chat/", json={"message": "Show my salary slip"})
    resp2 = client.post("/api/chat/", json={"message": "Show Devendra's salary slip"})
    assert resp1.json()["response"] == resp2.json()["response"]
