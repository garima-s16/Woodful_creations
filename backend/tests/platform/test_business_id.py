import re
from tests.helpers import _login

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def test_client_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Business ID Test Client", "phone": "9000010005"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["business_id"] is not None
    assert BUSINESS_ID_PATTERN.match(body["business_id"]), f"got {body['business_id']!r}"
    # The sequential code must still exist too - this is additive, not a replacement.
    assert body["client_code"].startswith("CL-")


def test_business_ids_are_unique_across_records(client, test_user):
    _login(client, test_user)
    ids = set()
    for i in range(5):
        resp = client.post("/api/clients/", json={"name": f"Uniqueness Test Client {i}", "phone": "9000010006"})
        ids.add(resp.json()["business_id"])
    assert len(ids) == 5


def test_material_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Business ID Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 2,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["material_code"].startswith("MAT-")


def test_supplier_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Business ID Test Supplier"})
    assert resp.status_code == 201
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_employee_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Business ID Test Employee", "department": "Production",
        "monthly_salary": "25000", "daily_wage": "1000",
    })
    assert resp.status_code == 201
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_order_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Business ID Client", "phone": "9000010007"}).json()["id"]
    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["order_code"].startswith("WC-")


def test_business_id_not_accepted_from_client_input(client, test_user):
    """The business_id must be server-generated, same guarantee as the
    sequential codes - a client-supplied value must be ignored."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Spoof Test Client", "business_id": "FAKE000001", "phone": "9000010008"})
    assert resp.status_code == 201
    assert resp.json()["business_id"] != "FAKE000001"
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_estimate_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Business ID Client", "phone": "9000010009"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000.00", "labor_cost": "20000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["estimate_code"].startswith("EST-")


def test_purchase_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Purchase Business ID Supplier"}).json()["id"]
    material_id = client.post("/api/materials/", json={
        "name": "Purchase Business ID Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 2,
    }).json()["id"]
    resp = client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier_id, "material_id": material_id,
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["purchase_code"].startswith("PUR-")


def test_payment_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Business ID Client", "phone": "9000010010"}).json()["id"]
    order_id = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()["id"]
    resp = client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_id,
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "5000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["receipt_code"].startswith("RCPT-")


def test_daily_task_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Business ID Employee", "department": "Production",
        "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    resp = client.post("/api/daily-tasks/", json={
        "date": "2026-08-05T00:00:00", "employee_id": employee_id, "task_description": "Sand and finish panels",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["task_code"].startswith("TSK-")


def test_production_job_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/production-jobs/", json={"date": "2026-08-05T00:00:00", "operation": "Cutting"})
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["job_code"].startswith("JOB-")


def test_project_expense_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Expense Business ID Client", "phone": "9000010011"}).json()["id"]
    order_id = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "15000.00", "advance": "0",
    }).json()["id"]
    resp = client.post("/api/project-expenses/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_id, "category": "Transport", "amount": "1200.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["expense_code"].startswith("EXP-")
