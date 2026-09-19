"""Tests for GET /api/suppliers/workspace - the compact Suppliers
command-center workspace endpoint added to extend the approved Orders/
Clients workspace layout to Suppliers. Covers response shape, search,
pagination, selected-record detail, the detail_only fast path, summary
aggregates, and role-based redaction of financial figures (mirrors the
existing SupplierDetailPage isPrivileged gating - never reimplemented,
only reused via the same is_privileged flag)."""
from tests.helpers import _login
from app.platform.security import hash_password
from app.modules.auth.auth import User


def _make_supplier(client, **overrides):
    payload = {"name": "Workspace Test Supplier", "category": "Wood"}
    payload.update(overrides)
    return client.post("/api/suppliers/", json=payload).json()


def _login_as_non_master(client, db_session, username="supplierwsuser", email="supplierwsuser@example.com"):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("NonMasterPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "NonMasterPass1!"})
    assert resp.status_code == 200
    return user


def test_suppliers_workspace_response_shape(client, test_user):
    _login(client, test_user)
    _make_supplier(client, name="Shape Check Supplier")

    resp = client.get("/api/suppliers/workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"summary", "suppliers", "selected_supplier"}
    assert set(data["suppliers"].keys()) == {"items", "total_count", "limit", "offset"}
    assert "total_suppliers" in data["summary"]
    assert "overview" in data["summary"] and "purchase_activity" in data["summary"]
    assert "payables_overview" in data["summary"] and "performance" in data["summary"]
    assert data["selected_supplier"] is None


def test_suppliers_workspace_search_matches_list_filter(client, test_user):
    """Search must match the same fields the plain supplier list/detail
    pages already key off: supplier_code, business_id, name, category,
    contact_person, phone."""
    _login(client, test_user)
    _make_supplier(client, name="Zanzibar Timber Co", contact_person="Priya Rao", phone="9998887771")
    _make_supplier(client, name="Unrelated Supplier")

    resp = client.get("/api/suppliers/workspace", params={"search": "Zanzibar"}).json()
    names = {s["name"] for s in resp["suppliers"]["items"]}
    assert "Zanzibar Timber Co" in names
    assert "Unrelated Supplier" not in names

    by_contact = client.get("/api/suppliers/workspace", params={"search": "Priya Rao"}).json()
    assert any(s["name"] == "Zanzibar Timber Co" for s in by_contact["suppliers"]["items"])


def test_suppliers_workspace_pagination_is_bounded(client, test_user):
    _login(client, test_user)
    for i in range(7):
        _make_supplier(client, name=f"Paginate Supplier {i}")

    resp = client.get("/api/suppliers/workspace", params={"search": "Paginate Supplier", "limit": 3, "offset": 0}).json()
    assert resp["suppliers"]["total_count"] == 7
    assert len(resp["suppliers"]["items"]) == 3
    assert resp["suppliers"]["limit"] == 3
    assert resp["suppliers"]["offset"] == 0

    page2 = client.get("/api/suppliers/workspace", params={"search": "Paginate Supplier", "limit": 3, "offset": 3}).json()
    assert len(page2["suppliers"]["items"]) == 3
    page1_ids = {s["id"] for s in resp["suppliers"]["items"]}
    page2_ids = {s["id"] for s in page2["suppliers"]["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_suppliers_workspace_selected_supplier_includes_purchase_and_materials(client, test_user):
    _login(client, test_user)
    supplier = _make_supplier(client, name="Selected Detail Supplier")
    material = client.post("/api/materials/", json={
        "name": "Workspace Detail Plywood", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-09-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "300.00", "gst_percent": "18", "payment_status": "Credit",
    })

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    selected = resp["selected_supplier"]
    assert selected is not None
    assert selected["id"] == supplier["id"]
    assert selected["purchase_summary"]["purchase_count"] == 1
    assert selected["purchase_summary"]["outstanding_invoice_count"] == 1
    assert len(selected["purchase_history"]) == 1


def test_suppliers_workspace_selected_supplier_missing_returns_none(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": 999999}).json()
    assert resp["selected_supplier"] is None


def test_suppliers_workspace_detail_only_skips_summary_and_list(client, test_user):
    """The detail_only fast path used on every row-selection change must
    never recompute summary/suppliers - only selected_supplier."""
    _login(client, test_user)
    supplier = _make_supplier(client, name="Detail Only Supplier")

    resp = client.get(
        "/api/suppliers/workspace",
        params={"selected_supplier_id": supplier["id"], "detail_only": True},
    ).json()
    assert resp["summary"] is None
    assert resp["suppliers"] is None
    assert resp["selected_supplier"] is not None
    assert resp["selected_supplier"]["id"] == supplier["id"]


def test_suppliers_workspace_summary_counts_are_authoritative(client, test_user):
    _login(client, test_user)
    supplier = _make_supplier(client, name="Summary Count Supplier")
    material = client.post("/api/materials/", json={
        "name": "Summary Count Material", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-09-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "1", "unit": "Kg", "rate": "100.00", "gst_percent": "18", "payment_status": "Part Paid",
    })

    resp = client.get("/api/suppliers/workspace").json()
    summary = resp["summary"]
    assert summary["suppliers_with_purchases"] >= 1
    assert summary["outstanding_invoice_count"] >= 1
    assert summary["outstanding_amount"] is not None  # master sees the real figure


def test_suppliers_workspace_hides_financial_figures_for_non_master(client, test_user, db_session):
    """Mirrors SupplierDetailPage's own existing isPrivileged gating -
    non-master users must never see outstanding_amount, total_purchased_value,
    purchase totals, or supplier prices, exactly as they already can't on
    the plain supplier detail page."""
    _login(client, test_user)
    supplier = _make_supplier(client, name="RBAC Supplier")
    material = client.post("/api/materials/", json={
        "name": "RBAC Material", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-09-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "1", "unit": "Kg", "rate": "100.00", "gst_percent": "18", "payment_status": "Paid",
    })

    _login_as_non_master(client, db_session)

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    assert resp["summary"]["outstanding_amount"] is None
    assert resp["summary"]["total_purchased_value"] is None
    selected = resp["selected_supplier"]
    assert selected["purchase_summary"]["total_purchased"] is None
    assert selected["purchase_summary"]["purchase_count"] is None
    assert selected["purchase_history"] == []
    # Non-financial identity info remains visible - not a blanket denial.
    assert selected["name"] == "RBAC Supplier"
