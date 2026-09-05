"""Shared test helpers - extracted from the ~120 test files that each
independently duplicated the exact same login helper. Import what's needed rather than
redefine it locally:

    from helpers import _login
"""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee_with_login(client, db_session, username, email):
    """Creates an Employee record, a linked non-master User account, and
    logs in as that user - returns the User row. Extracted from an
    exact, 13-line, zero-variation duplicate found independently in
    test_financial_rbac.py and test_inventory.py (both employee-daily-
    wage payload, both role="user", both immediately logging in) -
    genuinely the same helper, not two similar-looking ones."""
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    employee = client.post("/api/employees/", json={
        "name": username, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200
    return user
