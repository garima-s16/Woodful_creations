"""Test for a gap found closing the Tasks/Staff chain - the Task
Dashboard (staff_dashboard) had zero production job data despite the
brief explicitly requiring "Production/job status where applicable"."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_staff_dashboard_includes_production_status_summary(client, test_user):
    _login(client, test_user)
    order_client = client.post("/api/clients/", json={"name": "Staff Dashboard Production Client", "phone": "9000010184"}).json()
    order = client.post("/api/orders/", json={
        "client_id": order_client["id"], "order_date": "2026-08-18T00:00:00", "order_value": "50000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Staff Dashboard Production Employee", "monthly_salary": "20000"}).json()
    client.post("/api/production-jobs/", json={
        "date": "2026-08-18T00:00:00", "order_id": order["id"], "employee_id": employee["id"], "operation": "Cutting",
        "planned_qty": 10, "status": "In Progress",
    })

    resp = client.get("/api/dashboard/staff").json()
    assert "production_status_summary" in resp
    match = next((p for p in resp["production_status_summary"] if p["status"] == "In Progress"), None)
    assert match is not None
    assert match["count"] >= 1


def test_staff_dashboard_production_summary_reflects_real_counts_not_hardcoded(client, test_user):
    """Adding a second job in a different status must change the
    summary - proving it's derived from real data, not a fixed value."""
    _login(client, test_user)
    before = client.get("/api/dashboard/staff").json()["production_status_summary"]

    order_client = client.post("/api/clients/", json={"name": "Staff Dashboard Production Client 2", "phone": "9000010185"}).json()
    order = client.post("/api/orders/", json={
        "client_id": order_client["id"], "order_date": "2026-08-18T00:00:00", "order_value": "30000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Staff Dashboard Production Employee 2", "monthly_salary": "18000"}).json()
    client.post("/api/production-jobs/", json={
        "date": "2026-08-18T00:00:00", "order_id": order["id"], "employee_id": employee["id"], "operation": "Assembly",
        "planned_qty": 5, "status": "Pending",
    })

    after = client.get("/api/dashboard/staff").json()["production_status_summary"]
    assert after != before
