import re

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client, name="Salary Slip Test Employee"):
    resp = client.post("/api/employees/", json={
        "name": name, "designation": "Carpenter", "department": "Production", "monthly_salary": "26000.00",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_salary_slip_end_to_end(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "20000.00", "da": "2000.00", "hra": "3000.00", "overtime_amount": "500.00",
        "pf_deduction": "1200.00", "tds_deduction": "0.00", "other_deductions": "0.00",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    # 20000 + 2000 + 3000 + 500 - 1200 = 24300
    assert float(body["net_salary"]) == 24300.0


def test_salary_slip_defaults_working_and_paid_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "September", "year": "2026", "basic": "20000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["working_days"]) == 26.0
    assert float(body["paid_days"]) == 26.0


def test_salary_slip_rejects_paid_days_exceeding_working_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "October", "year": "2026",
        "working_days": "20", "paid_days": "25", "basic": "20000.00",
    })
    assert resp.status_code == 422


def test_salary_slip_rejects_zero_or_negative_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "November", "year": "2026",
        "working_days": "0", "paid_days": "0", "basic": "20000.00",
    })
    assert resp.status_code == 422


def test_duplicate_salary_slip_rejected(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    payload = {"employee_id": employee_id, "month": "December", "year": "2026", "basic": "20000.00"}

    first = client.post("/api/salary-slips/", json=payload)
    assert first.status_code == 201
    second = client.post("/api/salary-slips/", json=payload)
    assert second.status_code == 400


def test_salary_slip_update_rejects_paid_days_exceeding_working_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    create = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "January", "year": "2027",
        "working_days": "26", "paid_days": "26", "basic": "20000.00",
    })
    slip_id = create.json()["id"]

    resp = client.put(f"/api/salary-slips/{slip_id}", json={"working_days": "10"})
    assert resp.status_code == 400


def test_salary_slip_pdf_generates_successfully(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    create = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "February", "year": "2027", "basic": "20000.00",
    })
    slip_id = create.json()["id"]

    resp = client.get(f"/api/reports/salary-slips/{slip_id}.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0
