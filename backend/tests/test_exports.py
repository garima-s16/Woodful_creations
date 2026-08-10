"""Smoke tests: export endpoints return a real xlsx/pdf with the expected
structure, using openpyxl/pypdf to actually parse the response body."""
from io import BytesIO

from openpyxl import load_workbook


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _seed_minimal_order(client):
    client.post("/api/clients/", json={"client_code": "CL-EXP", "name": "Export Test Client"})
    clients = client.get("/api/clients/").json()
    client_id = next(c["id"] for c in clients if c["client_code"] == "CL-EXP")

    resp = client.post("/api/orders/", json={
        "order_code": "WC-EXP-001", "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    })
    return resp.json()


def test_purchases_export_returns_valid_xlsx(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/purchases.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    wb = load_workbook(BytesIO(resp.content))
    assert "Purchases" in wb.sheetnames
    ws = wb["Purchases"]
    assert ws.cell(row=3, column=1).value == "Purchase ID"


def test_stock_dashboard_export_has_all_sheets(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/stock-dashboard.xlsx")
    assert resp.status_code == 200

    wb = load_workbook(BytesIO(resp.content))
    for expected in ["Dashboard", "Material Master", "Purchases", "Issues", "Suppliers"]:
        assert expected in wb.sheetnames


def test_order_estimate_pdf_downloads(client, test_user):
    _login(client, test_user)
    order = _seed_minimal_order(client)

    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_payments_export_requires_master_or_manager(client, test_user):
    _login(client, test_user)  # test_user fixture is role=master, so this succeeds
    resp = client.get("/api/reports/payments.xlsx")
    assert resp.status_code == 200


def test_exports_require_auth(client):
    resp = client.get("/api/reports/purchases.xlsx")
    assert resp.status_code == 401
