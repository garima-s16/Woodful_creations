"""Regression tests for the confirmed defects/performance fixes:

1. Dashboard at-risk count now uses StockService.calculate_at_risk_orders
   (..., count_only=True) - the TRUE business-wide count - instead of
   len(orders) on the (bounded) display list, and must match the Orders
   workspace's own materials_at_risk KPI chip, which already used the
   same count_only path.
2/3. Supplier purchase history and supplier-material relationships are
   now bounded at the database (LIMIT) instead of an unbounded .all(),
   while purchase_count/total_purchased/outstanding_invoice_count stay
   computed via SQL aggregation over the FULL dataset.
4. Candidate interview history is now bounded the same way, while
   interview_count stays a full-dataset SQL COUNT.

Also guards that the active-order and OPEN_ESTIMATE_STATUSES
definitions these fixes sit on/near were not altered."""
from tests.helpers import _login
from app.platform.security import hash_password
from app.modules.auth.auth import User


def _make_client_row(client, name_suffix, phone_suffix):
    return client.post("/api/clients/", json={
        "name": f"Perf Regression Client {name_suffix}", "phone": f"92{phone_suffix:08d}",
    }).json()["id"]


def _make_at_risk_order(client, product_id, index):
    client_id = _make_client_row(client, index, index)
    return client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "1000", "product_id": product_id}],
    }).json()


# --- 1. Dashboard at-risk count -------------------------------------

def test_dashboard_at_risk_count_reflects_true_total_not_display_limit(client, test_user):
    """25 orders are genuinely at risk (a zero-stock material every one
    of them needs), the dashboard's display limit is 10: the count must
    be the true 25, never len(orders) capped at the display limit."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Dashboard Bounding Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "0",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Dashboard Bounding Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "1"}],
    }).json()
    for i in range(25):
        _make_at_risk_order(client, product["id"], i)

    resp = client.get("/api/dashboard/at-risk-orders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["at_risk_order_count"] == 25
    assert len(body["orders"]) == 10


def test_dashboard_at_risk_count_matches_orders_workspace_count(client, test_user):
    """Dashboard and the Orders workspace's own materials_at_risk KPI
    chip must report the identical true count - both now derive it from
    the same StockService.calculate_at_risk_orders(count_only=True)
    call, so they can never disagree about the same underlying data."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cross-Section Consistency Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "0",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Cross-Section Consistency Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "1"}],
    }).json()
    for i in range(3):
        _make_at_risk_order(client, product["id"], i)

    dashboard_count = client.get("/api/dashboard/at-risk-orders").json()["at_risk_order_count"]
    orders_workspace_count = client.get("/api/orders/workspace").json()["summary"]["materials_at_risk"]
    assert dashboard_count == orders_workspace_count == 3


# --- 2. Supplier purchase history bounding ---------------------------

def test_supplier_purchase_count_reflects_all_purchases_beyond_history_limit(client, test_user):
    """purchase_summary figures must reflect ALL 25 purchases even
    though purchase_history is bounded to the newest 20 - proving the
    aggregates are computed via SQL over the full dataset, never
    derived from the (now limited) history list."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "History Bounding Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "History Bounding Material", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    for i in range(25):
        client.post("/api/purchases/", json={
            "date": f"2026-01-{i + 1:02d}T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": "1", "unit": "Kg", "rate": "100.00", "gst_percent": "18", "payment_status": "Credit",
        })

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    selected = resp["selected_supplier"]
    assert selected["purchase_summary"]["purchase_count"] == 25
    assert selected["purchase_summary"]["outstanding_invoice_count"] == 25
    assert len(selected["purchase_history"]) == 20


def test_supplier_purchase_history_returns_newest_20_in_order(client, test_user):
    """The bounded history must be exactly the 20 most recent purchases,
    newest first - the same rows the old purchases[:20] Python slice
    (after an order_by date desc) used to return. Only the loading
    strategy changed (SQL LIMIT instead of an unbounded .all() then
    slicing in Python), never the result."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "History Order Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "History Order Material", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    created = []
    for i in range(25):
        purchase = client.post("/api/purchases/", json={
            "date": f"2026-02-{i + 1:02d}T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": "1", "unit": "Kg", "rate": "100.00", "gst_percent": "18", "payment_status": "Paid",
        }).json()
        created.append(purchase)

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    history_ids = [p["id"] for p in resp["selected_supplier"]["purchase_history"]]
    expected_ids = [p["id"] for p in created[-20:]][::-1]  # newest (highest date) first
    assert history_ids == expected_ids


def test_supplier_purchase_history_empty_for_non_master(client, test_user, db_session):
    """Redaction is unaffected by the bounding change - non-master
    viewers still get [] history and None aggregates, never the bounded
    rows/figures leaking through."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "History RBAC Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "History RBAC Material", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-01-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "1", "unit": "Kg", "rate": "100.00", "gst_percent": "18", "payment_status": "Paid",
    })

    user = User(
        username="historyrbacuser", email="historyrbacuser@example.com", full_name="History RBAC User",
        password_hash=hash_password("NonMasterPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "historyrbacuser@example.com", "password": "NonMasterPass1!"})

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    selected = resp["selected_supplier"]
    assert selected["purchase_history"] == []
    assert selected["purchase_summary"]["purchase_count"] is None


# --- 3. Supplier-material relationship bounding -----------------------

def test_supplier_materials_supplied_still_correct_at_normal_scale(client, test_user):
    """The SupplierMaterial query is now bounded (LIMIT), not an
    unbounded .all() - at ordinary scale (well under the bound) every
    linked material must still appear, unchanged."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Materials Bounding Supplier"}).json()
    material_ids = []
    for i in range(5):
        material = client.post("/api/materials/", json={
            "name": f"Materials Bounding Material {i}", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
        }).json()
        material_ids.append(material["id"])
        client.post("/api/supplier-materials/", json={
            "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "50.00",
        })

    resp = client.get("/api/suppliers/workspace", params={"selected_supplier_id": supplier["id"]}).json()
    linked_material_ids = {m["material_id"] for m in resp["selected_supplier"]["materials_supplied"]}
    assert linked_material_ids == set(material_ids)


# --- 4. Candidate interview history bounding --------------------------

def test_candidate_interview_count_reflects_all_interviews_beyond_history_limit(client, test_user):
    """interview_count must reflect ALL 25 interviews even though the
    interviews list is bounded to the newest 20."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={"name": "Interview Bounding Candidate"}).json()
    for i in range(25):
        client.post("/api/interviews/", json={
            "candidate_id": candidate["id"], "round": f"Round {i}",
            "scheduled_date": f"2026-03-{i + 1:02d}T10:00:00", "interviewer": "HR Manager",
        })

    resp = client.get("/api/candidates/workspace", params={"selected_candidate_id": candidate["id"]}).json()
    selected = resp["selected_candidate"]
    assert selected["interview_count"] == 25
    assert len(selected["interviews"]) == 20


def test_candidate_interview_history_returns_newest_20_in_order(client, test_user):
    """Same newest-first, bounded-at-the-database contract as the
    Supplier purchase history fix above."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={"name": "Interview Order Candidate"}).json()
    created = []
    for i in range(25):
        interview = client.post("/api/interviews/", json={
            "candidate_id": candidate["id"], "round": f"Round {i}",
            "scheduled_date": f"2026-04-{i + 1:02d}T10:00:00", "interviewer": "HR Manager",
        }).json()
        created.append(interview)

    resp = client.get("/api/candidates/workspace", params={"selected_candidate_id": candidate["id"]}).json()
    history_ids = [i["id"] for i in resp["selected_candidate"]["interviews"]]
    expected_ids = [i["id"] for i in created[-20:]][::-1]
    assert history_ids == expected_ids


def test_candidate_summary_interview_activity_still_counts_all_interviews(client, test_user):
    """The workspace-wide interview_activity.total_interviews summary
    (business-wide, separate from any one candidate's bounded history)
    must still count every interview - unaffected by bounding a single
    candidate's displayed history."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={"name": "Interview Summary Candidate"}).json()
    for i in range(22):
        client.post("/api/interviews/", json={
            "candidate_id": candidate["id"], "round": f"Round {i}",
            "scheduled_date": f"2026-05-{i + 1:02d}T10:00:00", "interviewer": "HR Manager",
        })

    resp = client.get("/api/candidates/workspace").json()
    assert resp["summary"]["interview_activity"]["total_interviews"] >= 22


# --- E/F. Definitions these fixes sit on/near must be unchanged -------

def test_active_order_filter_definition_unchanged(client, test_user):
    """Guards the exact business definition calculate_at_risk_orders'
    open_order_ids query depends on - Completed/Cancelled orders stay
    excluded, nothing else changed by touching the surrounding code."""
    from app.modules.sales.models import ORDER_TERMINAL_STATUSES
    assert ORDER_TERMINAL_STATUSES == ("Completed", "Cancelled")


def test_open_estimate_statuses_unchanged(client, test_user):
    from app.modules.sales.models import OPEN_ESTIMATE_STATUSES
    assert OPEN_ESTIMATE_STATUSES == ("draft", "sent", "changes_requested", "approved")
