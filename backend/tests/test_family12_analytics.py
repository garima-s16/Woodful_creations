"""Focused tests for Family 12 (Analytics & Reporting).

Scope, per the Family 12 brief: data scope, aggregation authorization,
drill-down authorization, export authorization, financial data
boundaries, HR data boundaries, and AI (chat) data boundaries. This is
NOT a general application security audit - it only covers the new
analytics surface (app/services/analytics_service.py,
app/api/routes/analytics.py, and the analytics-related chat handlers
in app/services/chat_service.py).
"""
from app.core.security import hash_password
from app.models.user import User


def _login(client, identifier="test@example.com", password="TestPass123!"):
    resp = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200
    return resp


def _create_employee_user(client, db_session, employee_id, username, email, password="EmpPass1!"):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password(password), role="user",
        employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _seed_master_data(client):
    """Creates one of everything Family 12 aggregates, using the real
    module endpoints (not direct DB inserts) so every figure analytics
    reports on is a genuine authoritative record."""
    client_obj = client.post("/api/clients/", json={"name": "Analytics Test Client", "phone": "9000010086"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_obj["id"], "order_date": "2026-06-01T00:00:00",
        "order_value": "100000", "advance": "20000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "amount": "10000", "payment_date": "2026-08-01T00:00:00",
    })
    supplier = client.post("/api/suppliers/", json={"name": "Analytics Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Analytics Test Ply", "unit": "Sheets", "opening_stock": "2",
        "minimum_stock": "10", "average_rate": "1500.00", "supplier_id": supplier["id"],
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "1500.00", "gst_percent": "18",
        "payment_status": "Pending",
    })
    client.post("/api/project-expenses/", json={
        "date": "2026-08-01T00:00:00", "order_id": order["id"], "category": "Raw Material",
        "amount": "5000",
    })
    return {"client": client_obj, "order": order, "supplier": supplier, "material": material}


def _make_non_master(client, db_session, name="Analytics RBAC Employee", username="analyticsrbacuser",
                      email="analyticsrbacuser@example.com"):
    employee = client.post("/api/employees/", json={"name": name}).json()
    _create_employee_user(client, db_session, employee["id"], username, email)
    _login(client, identifier=email, password="EmpPass1!")
    return employee


# --------------------------------------------------------------------- #
# Data scope
# --------------------------------------------------------------------- #
def test_master_only_domains_blocked_for_non_master(client, test_user, db_session):
    """sales, purchases, payments, expenses aggregate financial totals
    across every client/order - matching purchases.py / payments.py /
    project_expenses.py's own master-only gates."""
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/sales", "/api/analytics/purchases",
                 "/api/analytics/payments", "/api/analytics/expenses"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_open_domains_available_to_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/inventory", "/api/analytics/production",
                 "/api/analytics/projects", "/api/analytics/tasks",
                 "/api/analytics/workforce", "/api/analytics/operations"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_alerts_feed_excludes_master_only_domains_for_non_master(client, test_user, db_session):
    """The consolidated /alerts feed must not leak sales/purchases/expenses
    alerts to a non-master viewer, even though it fans out across every
    domain internally."""
    _login(client)
    # _seed_master_data's order is dated 2026-06-01, well over 60 days
    # before the current date, so the sales alert fires for master
    # without any extra setup.
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/alerts")
    assert resp.status_code == 200
    domains = {a["domain"] for a in resp.json()["alerts"]}
    assert domains.isdisjoint({"sales", "purchases", "expenses"})


# --------------------------------------------------------------------- #
# Aggregation authorization (financial figures nulled BEFORE the
# response is built, not stripped after the fact)
# --------------------------------------------------------------------- #
def test_inventory_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_stock_value"] is None
    assert all(c["stock_value"] is None for c in data["category_breakdown"])

    # Same call, as master, must show the real figure.
    _login(client)
    master_data = client.get("/api/analytics/inventory").json()
    assert master_data["total_stock_value"] is not None
    assert master_data["total_stock_value"] > 0


def test_operations_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/operations").json()
    assert resp["total_stock_value"] is None


# --------------------------------------------------------------------- #
# Financial data boundaries - project profitability
# --------------------------------------------------------------------- #
def test_project_profitability_hidden_from_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/projects").json()
    assert resp["order_profitability"] == []
    assert resp["overall_gross_margin_percent"] is None

    _login(client)
    master_resp = client.get("/api/analytics/projects").json()
    assert len(master_resp["order_profitability"]) >= 1
    assert master_resp["overall_gross_margin_percent"] is not None


# --------------------------------------------------------------------- #
# Drill-down authorization - the underlying records a KPI links to must
# obey the same scope as the KPI itself.
# --------------------------------------------------------------------- #
def test_outstanding_orders_drill_down_is_real_and_master_only(client, test_user, db_session):
    _login(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    # Non-master can't reach the drill-down data at all.
    assert client.get("/api/analytics/sales").status_code == 403

    _login(client)
    data = client.get("/api/analytics/sales").json()
    order_ids = {o["id"] for o in data["outstanding_orders"]}
    assert seed["order"]["id"] in order_ids
    # The outstanding total must equal the real Order.balance sum, not a
    # separately-invented figure.
    order_detail = client.get(f"/api/orders/{seed['order']['id']}").json()
    assert any(o["balance"] == float(order_detail["balance"]) for o in data["outstanding_orders"])


def test_low_stock_drill_down_visible_but_stock_value_not(client, test_user, db_session):
    _login(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    data = client.get("/api/analytics/inventory").json()
    material_ids = {m["id"] for m in data["low_stock_materials"]}
    assert seed["material"]["id"] in material_ids
    # Drill-down rows expose quantities, never a redacted-financial field.
    assert "stock_value" not in data["low_stock_materials"][0]


# --------------------------------------------------------------------- #
# Export authorization - export must inherit the same scope as on-screen.
# --------------------------------------------------------------------- #
def test_master_only_exports_blocked_for_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/reports/purchases.xlsx", "/api/reports/payments.xlsx",
                 "/api/reports/project-expenses.xlsx"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_orders_export_redacts_financial_columns_for_non_master(client, test_user, db_session):
    import io
    from openpyxl import load_workbook

    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/reports/orders.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    # Locate the actual header row (title/subtitle rows come first).
    header_row = []
    for row in ws.iter_rows(values_only=True):
        if row and "Client" in row:
            header_row = list(row)
            break
    assert "Order Value" not in header_row
    assert "Balance" not in header_row

    _login(client)
    master_resp = client.get("/api/reports/orders.xlsx")
    wb2 = load_workbook(io.BytesIO(master_resp.content))
    ws2 = wb2.active
    master_header = []
    for row in ws2.iter_rows(values_only=True):
        if row and "Client" in row:
            master_header = list(row)
            break
    assert "Order Value" in master_header
    assert "Balance" in master_header


# --------------------------------------------------------------------- #
# HR data boundaries
# --------------------------------------------------------------------- #
def test_workforce_non_master_sees_only_own_row(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    other_employee = client.post("/api/employees/", json={"name": "Other Workforce Employee"}).json()
    own_employee = _make_non_master(
        client, db_session, name="Own Workforce Employee",
        username="workforceown", email="workforceown@example.com",
    )

    resp = client.get("/api/analytics/workforce").json()
    ids_seen = {row["employee_id"] for row in resp["employee_performance"]}
    assert ids_seen == {own_employee["id"]}
    assert other_employee["id"] not in ids_seen

    _login(client)
    master_resp = client.get("/api/analytics/workforce").json()
    master_ids = {row["employee_id"] for row in master_resp["employee_performance"]}
    assert other_employee["id"] in master_ids
    assert own_employee["id"] in master_ids


# --------------------------------------------------------------------- #
# AI (chat) data boundaries - AI must use the same permission scope,
# never a shortcut around it because it queries the DB directly.
# --------------------------------------------------------------------- #
def test_ai_expense_explanation_blocked_for_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "why did expenses increase this month"})
    assert resp.status_code == 200
    assert "master accounts only" in resp.json()["response"].lower()


def test_ai_whats_changed_omits_financial_lines_for_non_master(client, test_user, db_session):
    _login(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert resp.status_code == 200
    text = resp.json()["response"].lower()
    assert "revenue" not in text
    assert "expenses are" not in text

    _login(client)
    master_resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert master_resp.status_code == 200


def test_ai_delayed_projects_grounded_in_real_projects_analytics(client, test_user, db_session):
    """The chatbot's delayed-projects answer must agree with what the
    Analytics page's own drill-down shows for the same underlying data -
    never a separately fabricated list."""
    _login(client)
    seed = _seed_master_data(client)
    client.put(f"/api/orders/{seed['order']['id']}", json={"project_status": "On Hold"})

    resp = client.post("/api/chat/", json={"message": "which projects are delayed"})
    assert resp.status_code == 200
    body = resp.json()
    record_paths = {r["path"] for r in body["records"]}
    assert f"/orders/{seed['order']['id']}" in record_paths

    analytics_resp = client.get("/api/analytics/projects").json()
    delayed_paths = {f"/orders/{p['id']}" for p in analytics_resp["delayed_projects"]}
    assert record_paths == delayed_paths
