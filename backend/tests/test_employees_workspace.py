"""Tests for GET /api/employees/workspace - the compact Employees
command-center workspace endpoint added to extend the approved Orders/
Clients workspace layout to Employees. Covers response shape, the
existing name/employee_code/designation/phone/email search filter,
department/status filters, pagination, selected-record detail, the
detail_only fast path, summary aggregates, and role-based salary/PAN/
UAN/bank-detail redaction (reused verbatim from _serialize_employees -
never reimplemented here)."""
from tests.helpers import _login, _create_employee_with_login


def _make_employee(client, **overrides):
    payload = {"name": "Workspace Test Employee", "monthly_salary": "25000"}
    payload.update(overrides)
    return client.post("/api/employees/", json=payload).json()


def test_employees_workspace_response_shape(client, test_user):
    _login(client, test_user)
    _make_employee(client, name="Shape Check Employee")

    resp = client.get("/api/employees/workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"summary", "employees", "selected_employee"}
    assert set(data["employees"].keys()) == {"items", "total_count", "limit", "offset"}
    assert "total_employees" in data["summary"]
    assert "attendance_availability" in data["summary"] and "department_role_mix" in data["summary"]
    assert data["selected_employee"] is None


def test_employees_workspace_search_matches_existing_list_filter(client, test_user):
    """Same fields as GET /api/employees/'s own search: name, employee_code,
    designation, phone, email."""
    _login(client, test_user)
    _make_employee(client, name="Zanzibar Carpenter", designation="Senior Carpenter", phone="9991112223")
    _make_employee(client, name="Unrelated Employee")

    resp = client.get("/api/employees/workspace", params={"search": "Zanzibar"}).json()
    names = {e["name"] for e in resp["employees"]["items"]}
    assert "Zanzibar Carpenter" in names
    assert "Unrelated Employee" not in names

    by_designation = client.get("/api/employees/workspace", params={"search": "Senior Carpenter"}).json()
    assert any(e["name"] == "Zanzibar Carpenter" for e in by_designation["employees"]["items"])


def test_employees_workspace_department_and_status_filters(client, test_user):
    _login(client, test_user)
    _make_employee(client, name="Dept Filter Employee", department="Production")
    _make_employee(client, name="Other Dept Employee", department="Sales")

    resp = client.get("/api/employees/workspace", params={"department": "Production"}).json()
    names = {e["name"] for e in resp["employees"]["items"]}
    assert "Dept Filter Employee" in names
    assert "Other Dept Employee" not in names

    active = client.get("/api/employees/workspace", params={"status": "Active"}).json()
    assert active["employees"]["total_count"] >= 1


def test_employees_workspace_pagination_is_bounded(client, test_user):
    _login(client, test_user)
    for i in range(7):
        _make_employee(client, name=f"Paginate Employee {i}")

    resp = client.get("/api/employees/workspace", params={"search": "Paginate Employee", "limit": 3, "offset": 0}).json()
    assert resp["employees"]["total_count"] == 7
    assert len(resp["employees"]["items"]) == 3

    page2 = client.get("/api/employees/workspace", params={"search": "Paginate Employee", "limit": 3, "offset": 3}).json()
    page1_ids = {e["id"] for e in resp["employees"]["items"]}
    page2_ids = {e["id"] for e in page2["employees"]["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_employees_workspace_selected_employee_detail(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, name="Selected Detail Employee")

    resp = client.get("/api/employees/workspace", params={"selected_employee_id": employee["id"]}).json()
    selected = resp["selected_employee"]
    assert selected is not None
    assert selected["id"] == employee["id"]
    assert selected["name"] == "Selected Detail Employee"


def test_employees_workspace_selected_employee_missing_returns_none(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/employees/workspace", params={"selected_employee_id": 999999}).json()
    assert resp["selected_employee"] is None


def test_employees_workspace_detail_only_skips_summary_and_list(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, name="Detail Only Employee")

    resp = client.get(
        "/api/employees/workspace",
        params={"selected_employee_id": employee["id"], "detail_only": True},
    ).json()
    assert resp["summary"] is None
    assert resp["employees"] is None
    assert resp["selected_employee"] is not None
    assert resp["selected_employee"]["id"] == employee["id"]


def test_employees_workspace_summary_attendance_counts_are_authoritative(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, name="Attendance Summary Employee")
    from datetime import datetime
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    client.post("/api/attendance/", json={
        "employee_id": employee["id"], "date": today, "attendance_status": "Present",
    })

    resp = client.get("/api/employees/workspace").json()
    assert resp["summary"]["present_today"] >= 1
    assert resp["summary"]["attendance_availability"]["present_today"] >= 1


def test_employees_workspace_redacts_salary_for_non_master(client, test_user, db_session):
    """Reuses _serialize_employees' existing redaction - non-master sees
    None for another employee's monthly_salary/daily_wage/PAN/UAN/bank
    details, both in the list and the selected-record detail panel."""
    _login(client, test_user)
    other_employee = _make_employee(client, name="RBAC Other Employee", monthly_salary="40000")

    _create_employee_with_login(client, db_session, "empworkspacerbacuser", "empworkspacerbacuser@example.com")

    resp = client.get(
        "/api/employees/workspace", params={"selected_employee_id": other_employee["id"]},
    ).json()
    list_row = next(e for e in resp["employees"]["items"] if e["id"] == other_employee["id"])
    assert list_row["monthly_salary"] is None
    assert list_row["daily_wage"] is None

    selected = resp["selected_employee"]
    assert selected["monthly_salary"] is None
    assert selected["pan"] is None
    assert selected["uan"] is None
    assert selected["bank_account_number"] is None
    # Non-financial directory info remains visible.
    assert selected["name"] == "RBAC Other Employee"


def test_employees_workspace_shows_own_salary_to_self(client, test_user, db_session):
    _login(client, test_user)
    employee = _make_employee(client, name="RBAC Self Employee", monthly_salary="21000")

    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    user = User(
        username="empworkspaceownrbac", email="empworkspaceownrbac@example.com", full_name="Emp Workspace Own",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "empworkspaceownrbac@example.com", "password": "EmpPass1!"})

    resp = client.get(
        "/api/employees/workspace", params={"selected_employee_id": employee["id"]},
    ).json()
    selected = resp["selected_employee"]
    assert selected["monthly_salary"] is not None
    assert float(selected["monthly_salary"]) == 21000.0
