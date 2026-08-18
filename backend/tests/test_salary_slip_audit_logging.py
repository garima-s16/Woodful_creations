"""Tests for salary slip audit logging - previously zero coverage on
the most sensitive HR/financial mutation in the app. Includes a
regression test for a real Decimal/JSON-serialization bug caught
during implementation: SalarySlip's numeric fields are Decimal
(Numeric columns), which a naive isinstance(x, (int, float)) check
silently misses, leaving a non-JSON-serializable value that would
crash the audit log commit."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_create_salary_slip_is_audit_logged(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Audit Test Employee"}).json()

    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "0", "hra": "6000", "overtime_amount": "0",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_salary_slip" and l["record_id"] == slip["id"]), None)
    assert match is not None
    assert match["new_value"]["employee_id"] == employee["id"]


def test_update_salary_slip_is_audit_logged_with_old_and_new_values(client, test_user):
    """The real regression guard - this must not raise a
    JSON-serialization error on commit, since basic/da/hra etc. are
    Decimal-typed Numeric columns, not plain floats."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Audit Update Employee"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "0", "hra": "6000", "overtime_amount": "0",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    resp = client.put(f"/api/salary-slips/{slip['id']}", json={"basic": "10000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_salary_slip" and l["record_id"] == slip["id"]), None)
    assert match is not None
    assert match["old_value"]["basic"] == 9500.0
    assert match["new_value"]["basic"] == 10000.0
