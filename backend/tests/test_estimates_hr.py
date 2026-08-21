def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_estimate_computes_tax_and_total(client, test_user):
    _login(client, test_user)
    create_resp = client.post("/api/clients/", json={"name": "Estimate Client", "phone": "9000010076"})
    client_id = create_resp.json()["id"]

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "material_cost": "50000.00", "labor_cost": "20000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["tax_amount"]) == 12600.0
    assert float(body["total_cost"]) == 82600.0


def test_candidate_and_interview_flow(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Test Candidate", "position": "CNC Operator"})
    assert resp.status_code == 201
    candidate_id = resp.json()["id"]

    resp = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "round": "Round 1",
        "scheduled_date": "2026-08-15T10:00:00", "interviewer": "Nikhil",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Scheduled"


def test_salary_slip_computes_net(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "employee_code": "EMP-SAL", "name": "Salary Test Employee", "monthly_salary": "20000.00",
    })
    employee_id = resp.json()["id"]

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "August", "year": "2026",
        "basic": "15000.00", "da": "2000.00", "hra": "3000.00",
        "pf_deduction": "1800.00", "tds_deduction": "0.00",
    })
    assert resp.status_code == 201
    assert float(resp.json()["net_salary"]) == 18200.0


def test_candidates_require_master_or_manager(client):
    resp = client.get("/api/candidates/")
    assert resp.status_code == 401


def test_chat_endpoint_answers_stock_question(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "how is my stock looking"})
    assert resp.status_code == 200
    assert "materials" in resp.json()["response"].lower()
