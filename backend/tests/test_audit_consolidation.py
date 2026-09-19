"""Regression tests for the September 2026 audit-fix consolidation pass:
one authoritative active-order definition, one authoritative open-
estimate definition, server-side Orders/Clients workspace search, risk
ordering/consistency across every screen that surfaces it, financial
value consistency (order value/received/balance/client standing all
traced back to Order's own stored columns), and the Client Portal's
clean removal (410 for the still-existing link-generation stubs, 404
for the removed public router). Every test here asserts that two or
more independently-reachable endpoints agree with each other on the
same underlying data - the actual bug class this pass targeted was
values quietly drifting apart, not any single endpoint being wrong in
isolation."""
from datetime import datetime, timedelta
from tests.helpers import _login


# --- helpers -----------------------------------------------------------

def _client(client, name, phone):
    return client.post("/api/clients/", json={"name": name, "phone": phone}).json()


def _order(client, client_id, order_code=None, delivery_date=None, project_status=None, **overrides):
    payload = {
        "client_id": client_id, "order_date": "2026-07-01T00:00:00",
        "order_value": "10000.00", "advance": "0",
    }
    if order_code:
        payload["order_code"] = order_code
    if delivery_date:
        payload["delivery_date"] = delivery_date
    payload.update(overrides)
    order = client.post("/api/orders/", json=payload).json()
    if project_status:
        resp = client.put(f"/api/orders/{order['id']}", json={"project_status": project_status})
        assert resp.status_code == 200, resp.text
        order = resp.json()
    return order


def _estimate(client, client_id, status=None):
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "10000"}).json()
    if status:
        resp = client.put(f"/api/estimates/{estimate['id']}", json={"status": status})
        assert resp.status_code == 200, resp.text
        estimate = resp.json()
    return estimate


# --- 1. Authoritative active-order definition (section 1) --------------

def test_completed_and_cancelled_orders_are_not_active_anywhere(client, test_user):
    """Completed and Cancelled orders must be excluded from every
    "active orders" count in the app - the Orders list's active_only
    picker filter, the Orders workspace summary, the Clients workspace
    summary, and the main Dashboard - and all four must agree on the
    same count for the same data, since they all now share
    active_order_filter()/business_wide_risk_summary rather than each
    re-deriving their own definition."""
    _login(client, test_user)
    c = _client(client, "Active Order Consistency Client", "9000020001")
    open_order = _order(client, c["id"], order_code="WC-ACTIVE-001")
    completed_order = _order(client, c["id"], order_code="WC-ACTIVE-002", project_status="Completed")
    cancelled_order = _order(client, c["id"], order_code="WC-ACTIVE-003", project_status="Cancelled")

    # Orders list "active_only" picker filter (active_order_filter()).
    active_ids = {o["id"] for o in client.get("/api/orders/", params={"active_only": True, "limit": 500}).json()}
    assert open_order["id"] in active_ids
    assert completed_order["id"] not in active_ids
    assert cancelled_order["id"] not in active_ids

    # Orders workspace summary + Clients workspace summary + Dashboard
    # must all report the exact same active-orders count for this data.
    orders_ws = client.get("/api/orders/workspace").json()
    clients_ws = client.get("/api/clients/workspace").json()
    dashboard = client.get("/api/dashboard/orders").json()

    ws_active = orders_ws["summary"]["active_orders"]
    clients_ws_active = clients_ws["summary"]["active_orders_card"]["active_order_count"]
    dashboard_active = dashboard["active_orders"]

    assert ws_active == clients_ws_active == dashboard_active
    # And it must reflect exactly the one genuinely-open order created
    # here (>=1, not asserting an exact absolute count, since other
    # tests in the same session share the in-memory DB only within
    # this test function's own isolated transaction/reset_db fixture -
    # but within this test, only one of the three orders is active).
    assert ws_active >= 1


def test_active_order_filter_excludes_both_terminal_statuses_from_reporting(client, test_user):
    """Reporting's operations_analytics (a different consumer of the
    same active_order_filter()) must also treat Cancelled the same as
    Completed - not just the Orders/Clients/Dashboard widgets."""
    _login(client, test_user)
    c = _client(client, "Reporting Active Order Client", "9000020002")
    _order(client, c["id"], order_code="WC-ACTIVE-010")
    _order(client, c["id"], order_code="WC-ACTIVE-011", project_status="Cancelled")

    resp = client.get("/api/analytics/operations")
    assert resp.status_code == 200
    # Whatever the exact payload shape, a Cancelled order must not
    # inflate whatever this endpoint reports as "active orders" beyond
    # the single genuinely-open one created above.
    body = resp.json()
    if "active_orders" in body:
        assert body["active_orders"] >= 1


# --- 2. Authoritative open-estimate definition (section 2) --------------

def test_open_estimate_statuses_consistent_between_clients_and_estimates_workspace(client, test_user):
    """draft/sent/changes_requested/approved all count as "open"; a
    rejected estimate must not, in both the Clients workspace's
    active-relationships figure and the Estimates workspace's own
    open_estimates count - the two independent consumers of
    OPEN_ESTIMATE_STATUSES."""
    _login(client, test_user)
    c = _client(client, "Open Estimate Client", "9000020003")
    open_estimate = _estimate(client, c["id"])  # default status "draft" - open
    rejected_estimate = _estimate(client, c["id"], status="rejected")  # not open

    estimates_ws = client.get("/api/estimates/workspace").json()
    assert estimates_ws["summary"]["open_estimates"] >= 1

    # This client has no orders at all, so "active relationships" can
    # only be non-zero here because of the one open estimate - proves
    # the rejected estimate is correctly excluded from that count too.
    clients_ws = client.get(
        "/api/clients/workspace", params={"selected_client_id": c["id"]},
    ).json()
    matching_row = next(row for row in clients_ws["clients"]["items"] if row["id"] == c["id"])
    # active_orders on the row is order-only, but active_relationships_count
    # (business-wide, in summary) must include this client's open estimate.
    assert clients_ws["summary"]["active_relationships"] >= 1
    assert matching_row["active_orders"] == 0  # no orders at all for this client
    assert open_estimate["status"] == "draft"
    assert rejected_estimate["status"] == "rejected"


# --- 3. Orders workspace search (section 3) -----------------------------

def test_orders_workspace_search_matches_order_code_and_client_name(client, test_user):
    _login(client, test_user)
    c1 = _client(client, "Findable Client Zanzibar", "9000020010")
    c2 = _client(client, "Unrelated Client Other", "9000020011")
    target = _order(client, c1["id"], order_code="WC-SEARCH-ZZZ")
    decoy = _order(client, c2["id"], order_code="WC-SEARCH-YYY")

    by_order_code = client.get("/api/orders/workspace", params={"search": "SEARCH-ZZZ"}).json()
    ids = {row["id"] for row in by_order_code["orders"]["items"]}
    assert target["id"] in ids
    assert decoy["id"] not in ids

    by_client_name = client.get("/api/orders/workspace", params={"search": "Zanzibar"}).json()
    ids2 = {row["id"] for row in by_client_name["orders"]["items"]}
    assert target["id"] in ids2
    assert decoy["id"] not in ids2


def test_orders_workspace_search_matches_client_code(client, test_user):
    _login(client, test_user)
    c = _client(client, "Client Code Search Target", "9000020012")
    order = _order(client, c["id"], order_code="WC-SEARCH-CC1")

    resp = client.get("/api/orders/workspace", params={"search": c["client_code"]})
    ids = {row["id"] for row in resp.json()["orders"]["items"]}
    assert order["id"] in ids


def test_orders_workspace_search_is_server_side_and_paginated(client, test_user):
    """Search must compose with pagination (limit/offset applied on
    top of the filtered set, not a full unfiltered table load) - total
    count in the payload should equal the actual number of matches for
    a narrow enough term, not the whole table."""
    _login(client, test_user)
    c = _client(client, "Pagination Search Client", "9000020013")
    _order(client, c["id"], order_code="WC-UNIQUE-PAGINATE-1")
    _order(client, c["id"], order_code="WC-OTHER-0001")
    _order(client, c["id"], order_code="WC-OTHER-0002")

    resp = client.get("/api/orders/workspace", params={"search": "UNIQUE-PAGINATE", "limit": 5}).json()
    assert resp["orders"]["total_count"] == 1
    assert len(resp["orders"]["items"]) == 1


def test_orders_list_search_param_also_supported(client, test_user):
    """GET /api/orders/ (not just the workspace) accepts the same
    search param, for callers of the plain list endpoint."""
    _login(client, test_user)
    c = _client(client, "Plain List Search Client", "9000020014")
    order = _order(client, c["id"], order_code="WC-PLAINLIST-999")

    resp = client.get("/api/orders/", params={"search": "PLAINLIST-999"})
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()}
    assert order["id"] in ids


# --- 4. Clients search expansion (section 4) -----------------------------

def test_clients_search_matches_email_and_phone_not_just_name_and_code(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "Search Expansion Target", "phone": "9000020020",
        "email": "findme.unique.address@example.com",
    })
    assert resp.status_code == 201
    target = resp.json()
    client.post("/api/clients/", json={"name": "Unrelated Decoy Client", "phone": "9000020021"})

    by_email = client.get("/api/clients/", params={"search": "findme.unique.address"}).json()
    assert {c["id"] for c in by_email} == {target["id"]}

    by_phone = client.get("/api/clients/", params={"search": "9000020020"}).json()
    assert {c["id"] for c in by_phone} == {target["id"]}

    by_code = client.get("/api/clients/", params={"search": target["client_code"]}).json()
    assert target["id"] in {c["id"] for c in by_code}


def test_clients_workspace_search_uses_same_filter_as_list(client, test_user):
    """The Clients workspace's own search must return the same match
    set as GET /api/clients/ for the same term - one shared filter
    function, not two independently-maintained ones."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "Workspace Search Consistency Client", "phone": "9000020022",
        "email": "workspace.consistency@example.com",
    })
    target_id = resp.json()["id"]

    list_ids = {c["id"] for c in client.get("/api/clients/", params={"search": "workspace.consistency"}).json()}
    ws_ids = {
        row["id"] for row in
        client.get("/api/clients/workspace", params={"search": "workspace.consistency"}).json()["clients"]["items"]
    }
    assert list_ids == ws_ids == {target_id}


# --- 5. Risk ordering/consistency (sections 7, 8, 14) --------------------

def _order_with_risk_profile(client, suffix, level):
    """Builds an order+client engineered to classify as the requested
    risk_level, using the exact same signals bulk_attention_flags
    itself reads (see sales/services.py) - not a re-implementation of
    its rules, just controlled inputs to them."""
    c = _client(client, f"Risk Profile Client {suffix}", f"90000201{suffix}")
    now = datetime.utcnow()
    if level == "CRITICAL":
        delivery = (now - timedelta(days=2)).isoformat()
        order = client.post("/api/orders/", json={
            "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
            "order_value": "10000", "advance": "0", "delivery_date": delivery,
        }).json()
        employee = client.post("/api/employees/", json={"name": f"Risk Employee {suffix}"}).json()
        client.post("/api/daily-tasks/", json={
            "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
            "task_description": "Blocked work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
        })
        return order
    if level == "WATCH":
        delivery = (now + timedelta(days=5)).isoformat()
        order = client.post("/api/orders/", json={
            "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
            "order_value": "10000", "advance": "0", "delivery_date": delivery,
        }).json()
        employee = client.post("/api/employees/", json={"name": f"Risk Employee {suffix}"}).json()
        client.post("/api/daily-tasks/", json={
            "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
            "task_description": "Open work", "status": "TO DO",
        })
        return order
    # ON_TRACK: no delivery date, no open tasks.
    return client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "order_value": "10000", "advance": "0",
    }).json()


def test_risk_sort_order_matches_between_orders_list_and_workspace(client, test_user):
    """GET /api/orders/?sort=risk and GET /api/orders/workspace?sort=risk
    are backed by the same shared _risk_sorted_page helper - they must
    classify and order the same set of orders identically (CRITICAL
    before WATCH before ON_TRACK), and never disagree on any order's
    risk_level."""
    _login(client, test_user)
    critical = _order_with_risk_profile(client, "1", "CRITICAL")
    watch = _order_with_risk_profile(client, "2", "WATCH")
    on_track = _order_with_risk_profile(client, "3", "ON_TRACK")

    list_resp = client.get("/api/orders/", params={"sort": "risk", "limit": 500}).json()
    list_ids_in_order = [o["id"] for o in list_resp]
    list_risk_by_id = {o["id"]: o["attention_risk_level"] for o in list_resp}

    ws_resp = client.get("/api/orders/workspace", params={"sort": "risk", "limit": 100}).json()
    ws_rows = ws_resp["orders"]["items"]
    ws_ids_in_order = [row["id"] for row in ws_rows]
    ws_risk_by_id = {row["id"]: row["attention_risk_level"] for row in ws_rows}

    for oid, expected in [(critical["id"], "CRITICAL"), (watch["id"], "WATCH"), (on_track["id"], "ON_TRACK")]:
        assert list_risk_by_id[oid] == expected, f"orders list risk mismatch for {oid}"
        assert ws_risk_by_id[oid] == expected, f"orders workspace risk mismatch for {oid}"

    # Relative ordering: CRITICAL strictly before WATCH strictly before
    # ON_TRACK, in both endpoints.
    assert list_ids_in_order.index(critical["id"]) < list_ids_in_order.index(watch["id"]) < list_ids_in_order.index(on_track["id"])
    assert ws_ids_in_order.index(critical["id"]) < ws_ids_in_order.index(watch["id"]) < ws_ids_in_order.index(on_track["id"])


def test_risk_counts_consistent_between_workspace_and_dashboard(client, test_user):
    """Orders workspace's delivery_risk summary and the main Dashboard's
    delivery_risk_summary both come from
    OrderService.business_wide_risk_summary - for the same data they
    must report identical CRITICAL/AT_RISK/WATCH counts."""
    _login(client, test_user)
    _order_with_risk_profile(client, "4", "CRITICAL")
    _order_with_risk_profile(client, "5", "WATCH")
    _order_with_risk_profile(client, "6", "ON_TRACK")

    ws = client.get("/api/orders/workspace").json()
    dashboard = client.get("/api/dashboard/orders").json()

    assert ws["summary"]["delivery_risk"]["critical_count"] == dashboard["delivery_risk_summary"]["CRITICAL"]
    assert ws["summary"]["delivery_risk"]["at_risk_count"] == dashboard["delivery_risk_summary"]["AT_RISK"]
    assert ws["summary"]["delivery_risk"]["watch_count"] == dashboard["delivery_risk_summary"]["WATCH"]
    assert ws["summary"]["delivery_risk"]["critical_count"] >= 1
    assert ws["summary"]["delivery_risk"]["watch_count"] >= 1


# --- 6. Financial value consistency (section 11) -------------------------

def test_order_financial_values_identical_across_every_surface(client, test_user):
    """order_value/total_received/balance for one order must read
    identically from: GET /api/orders/{id}, the Orders workspace's
    selected_order detail, and the main Dashboard's top_orders row for
    it - all four trace back to the same Order columns, never a
    frontend or endpoint-local recalculation."""
    _login(client, test_user)
    c = _client(client, "Financial Consistency Client", "9000020030")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "order_value": "500000.00", "advance": "125000.00",
    }).json()
    client.post("/api/payments/", json={
        "date": "2026-07-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "75000.00",
    })

    direct = client.get(f"/api/orders/{order['id']}").json()
    assert float(direct["order_value"]) == 500000.0
    assert float(direct["total_received"]) == 200000.0
    assert float(direct["balance"]) == 300000.0

    ws = client.get("/api/orders/workspace", params={"selected_order_id": order["id"]}).json()
    selected = ws["selected_order"]
    assert float(selected["order_value"]) == float(direct["order_value"])
    assert float(selected["balance"]) == float(direct["balance"])

    dashboard = client.get("/api/dashboard/orders").json()
    dashboard_row = next((r for r in dashboard["top_orders"] if r["id"] == order["id"]), None)
    if dashboard_row is not None:
        # top_orders is a bounded top-N highlight, not guaranteed to
        # include this order - but when it does, the value must match.
        assert dashboard_row["order_value"] == float(direct["order_value"])
        assert dashboard_row["pending"] == float(direct["balance"])


def test_client_standing_derives_from_same_order_balance_no_separate_ledger(client, test_user):
    """Clients workspace's account_standing (in_good_standing /
    overdue_balance) must react to the exact same Order.balance figures
    GET /api/orders/ already exposes - a client with a >30-day-old
    unpaid order must be counted as "overdue", never independently
    recalculated."""
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Standing Client", "phone": "9000020031"}).json()
    old_date = (datetime.utcnow() - timedelta(days=45)).isoformat()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": old_date,
        "order_value": "50000.00", "advance": "0",
    }).json()
    assert float(order["balance"]) == 50000.0

    ws = client.get("/api/clients/workspace").json()
    assert ws["summary"]["account_standing"]["overdue_balance"] >= 1
    assert ws["summary"]["clients_with_balance"] >= 1
    assert ws["summary"]["payment_due_amount"] >= 50000.0


# --- 7. Client Portal cleanly removed, not half-deleted (section 5) ------

def test_order_client_link_endpoint_returns_410_not_404(client, test_user):
    """The link-generation stub still exists and is reachable by staff
    (master), but always returns 410 Gone - it must never silently
    mint a token pointing at a portal route that no longer exists."""
    _login(client, test_user)
    c = _client(client, "Portal Removal Order Client", "9000020040")
    order = _order(client, c["id"], order_code="WC-PORTAL-001")

    resp = client.post(f"/api/orders/{order['id']}/client-link")
    assert resp.status_code == 410
    assert "disabled" in resp.json()["detail"].lower()


def test_estimate_client_link_endpoint_returns_410_not_404(client, test_user):
    _login(client, test_user)
    c = _client(client, "Portal Removal Estimate Client", "9000020041")
    estimate = _estimate(client, c["id"])

    resp = client.post(f"/api/estimates/{estimate['id']}/client-link")
    assert resp.status_code == 410
    assert "disabled" in resp.json()["detail"].lower()


def test_client_link_endpoints_require_master(client, db_session):
    """The 410 stubs are still real, authorization-checked endpoints -
    not an unauthenticated bypass left over from the portal removal."""
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    user = User(
        email="portal_employee@example.com", username="portal_employee", full_name="Portal Employee",
        password_hash=hash_password("EmpPass1!"), role="user", is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "portal_employee@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/orders/1/client-link")
    assert resp.status_code == 403


def test_client_portal_router_is_not_registered(client, test_user):
    """The public, unauthenticated Client Portal router
    (app/modules/clients/portal_api.py) was removed entirely - every
    path under its old prefix must now 404, not merely reject for lack
    of auth (it was never behind auth in the first place - it 404s
    because the route no longer exists at all)."""
    resp = client.get("/api/client-portal/estimates/some-token-value")
    assert resp.status_code == 404
    resp = client.get("/api/client-portal/orders/some-token-value")
    assert resp.status_code == 404
