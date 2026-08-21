"""Family 12 gap-fix: /api/reports/orders/{id}/estimate.pdf and
/api/reports/estimates/{id}/quote.pdf previously used get_current_user,
so any authenticated role (not just master) could download a PDF
containing order_value/total_received and per-line-item rate/amount -
the exact fields test_order_financial_rbac.py / test_estimate_financial_rbac.py
already prove are nulled for non-master through the JSON API. Both
routes are now require_role("master"), matching invoice.pdf.
"""
from app.core.security import hash_password
from app.models.user import User


def _login_master(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_and_login_employee(client, db_session, username, email):
    employee = client.post("/api/employees/", json={"name": "PDF RBAC Employee", "monthly_salary": "20000"}).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def _seed_order(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Client", "phone": "9000010073"}).json()["id"]
    return client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()


def _seed_estimate(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Estimate Client", "phone": "9000010074"}).json()["id"]
    return client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "30000", "labor_cost": "10000",
    }).json()


def test_master_can_download_order_estimate_pdf(client, test_user):
    _login_master(client, test_user)
    order = _seed_order(client)
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_order_estimate_pdf(client, test_user, db_session):
    _login_master(client, test_user)
    order = _seed_order(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser1", "pdfrbacuser1@example.com")
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 403


def test_master_can_download_estimate_quote_pdf(client, test_user):
    _login_master(client, test_user)
    estimate = _seed_estimate(client)
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_estimate_quote_pdf(client, test_user, db_session):
    _login_master(client, test_user)
    estimate = _seed_estimate(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser2", "pdfrbacuser2@example.com")
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 403


def test_pdf_exports_require_auth(client):
    resp = client.get("/api/reports/orders/1/estimate.pdf")
    assert resp.status_code == 401
    resp = client.get("/api/reports/estimates/1/quote.pdf")
    assert resp.status_code == 401
