"""Tests that the salary slip PDF endpoint actually generates a valid
PDF response for real stored data, not just that permissions are
enforced (covered separately in test_salary_slip_pdf_rbac.py)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_salary_slip_pdf_generates_successfully(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen Test Employee", "monthly_salary": "20000",
        "designation": "Carpenter", "department": "Assembly",
        "pan": "ABCPT1234A", "uan": "100200300999",
        "bank_name": "State Bank of India", "bank_account_number": "998877661234",
        "tax_regime": "New",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "500", "hra": "6000", "overtime_amount": "1500",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000  # a genuine PDF, not an empty/error stub


def test_salary_slip_pdf_generates_with_no_leave_history(client, test_user):
    """An employee with zero leave records must not crash the PDF -
    the Leave Balance section should degrade gracefully."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen No Leave Employee", "monthly_salary": "18000",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200


def test_salary_slip_pdf_generates_with_missing_employee_payroll_fields(client, test_user):
    """PAN/UAN/bank details are all optional - a slip for an employee
    without them must still generate cleanly (shown as '-')."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen Minimal Employee", "monthly_salary": "14000",
    }).json()
    assert employee.get("pan") is None
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "7000", "da": "0", "hra": "3000", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "200",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200
