def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client):
    resp = client.post("/api/employees/", json={
        "employee_code": "EMP-LEAVE", "name": "Leave Test Employee", "monthly_salary": "18000.00",
    })
    return resp.json()["id"]


def test_leave_request_and_default_status(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "CL",
        "start_date": "2026-08-20T00:00:00", "end_date": "2026-08-21T00:00:00", "days": "2",
        "reason": "Family function",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Pending"


def test_leave_rejects_end_before_start(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "SL",
        "start_date": "2026-08-20T00:00:00", "end_date": "2026-08-18T00:00:00", "days": "1",
    })
    assert resp.status_code == 400


def test_leave_approval_updates_status(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    create = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "PL",
        "start_date": "2026-09-01T00:00:00", "end_date": "2026-09-02T00:00:00", "days": "2",
    })
    leave_id = create.json()["id"]

    resp = client.put(f"/api/leaves/{leave_id}", json={"status": "Approved", "approved_by": "Nikhil"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Approved"


def test_leaves_require_auth(client):
    resp = client.get("/api/leaves/")
    assert resp.status_code == 401
