from datetime import datetime, timedelta
def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_material(client, name, current=None, minimum=5):
    resp = client.post("/api/materials/", json={
        "name": name, "unit": "Sheets", "opening_stock": current if current is not None else 20, "minimum_stock": minimum,
    })
    return resp.json()


def test_no_limit_returns_everything_unpaginated(client, test_user):
    _login(client, test_user)
    for i in range(5):
        _create_material(client, f"Unpaginated Material {i}")

    resp = client.get("/api/materials/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 5
    # Backward compatible - no pagination metadata forced on old callers.
    assert "X-Total-Count" in resp.headers


def test_limit_and_offset_actually_paginate(client, test_user):
    _login(client, test_user)
    for i in range(8):
        _create_material(client, f"Page Test Material {i}")

    page1 = client.get("/api/materials/", params={"limit": 3, "offset": 0})
    page2 = client.get("/api/materials/", params={"limit": 3, "offset": 3})

    assert len(page1.json()) == 3
    assert len(page2.json()) == 3
    ids_page1 = {m["id"] for m in page1.json()}
    ids_page2 = {m["id"] for m in page2.json()}
    assert ids_page1.isdisjoint(ids_page2)

    total = int(page1.headers["X-Total-Count"])
    assert total == int(page2.headers["X-Total-Count"])
    assert total >= 8


def test_low_stock_filter_composes_correctly_with_pagination(client, test_user):
    """Regression test: low_stock_only used to be filtered in Python
    AFTER the query ran, which would have silently broken once SQL-level
    pagination was added (a page could come back with fewer or zero
    matching rows even though more existed). This confirms the total
    count and the paginated page both reflect the SQL-level filter."""
    _login(client, test_user)
    _create_material(client, "Low Stock Regression A", current=1, minimum=10)
    _create_material(client, "Low Stock Regression B", current=2, minimum=10)
    _create_material(client, "Well Stocked Regression C", current=50, minimum=10)

    resp = client.get("/api/materials/", params={"low_stock_only": True, "limit": 1, "offset": 0})
    assert resp.status_code == 200
    total = int(resp.headers["X-Total-Count"])
    assert total >= 2  # both low-stock materials counted, not just what fit on this page
    assert len(resp.json()) == 1  # the page itself respects the limit
    assert resp.json()[0]["current_stock"] <= resp.json()[0]["minimum_stock"]


def _login2(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_orders_pagination_backward_compatible_without_limit(client, test_user):
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Page Test Client"}).json()["id"]
    for i in range(4):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
        })

    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4
    assert "X-Total-Count" in resp.headers


def test_orders_limit_and_offset_paginate_correctly(client, test_user):
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Page Test Client 2"}).json()["id"]
    for i in range(6):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "5000.00", "advance": "0",
        })

    page1 = client.get("/api/orders/", params={"client_id": client_id, "limit": 2, "offset": 0})
    page2 = client.get("/api/orders/", params={"client_id": client_id, "limit": 2, "offset": 2})
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    ids1 = {o["id"] for o in page1.json()}
    ids2 = {o["id"] for o in page2.json()}
    assert ids1.isdisjoint(ids2)
    assert int(page1.headers["X-Total-Count"]) == 6


def test_orders_pagination_composes_with_client_id_filter(client, test_user):
    """Regression check: client_id filtering must still correctly scope
    the total count and the page - not just return the first N orders
    system-wide."""
    _login2(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "Filter Test Client A"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "Filter Test Client B"}).json()["id"]

    for i in range(3):
        client.post("/api/orders/", json={
            "client_id": client_a, "order_date": "2026-08-01T00:00:00", "order_value": "1000.00", "advance": "0",
        })
    client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-01T00:00:00", "order_value": "2000.00", "advance": "0",
    })

    resp = client.get("/api/orders/", params={"client_id": client_a, "limit": 10, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 3
    assert len(resp.json()) == 3
    assert all(o["client_id"] == client_a for o in resp.json())


def test_clients_pagination_backward_compatible_without_limit(client, test_user):
    _login2(client, test_user)
    for i in range(4):
        client.post("/api/clients/", json={"name": f"Client Page Test {i}"})

    resp = client.get("/api/clients/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4
    assert "X-Total-Count" in resp.headers


def test_clients_limit_and_offset_paginate_correctly(client, test_user):
    _login2(client, test_user)
    for i in range(5):
        client.post("/api/clients/", json={"name": f"Client Paginate Test {i}"})

    page1 = client.get("/api/clients/", params={"limit": 2, "offset": 0})
    page2 = client.get("/api/clients/", params={"limit": 2, "offset": 2})
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    names1 = {c["id"] for c in page1.json()}
    names2 = {c["id"] for c in page2.json()}
    assert names1.isdisjoint(names2)


def test_clients_pagination_composes_with_search_filter(client, test_user):
    _login2(client, test_user)
    client.post("/api/clients/", json={"name": "Searchable Pagination Match One"})
    client.post("/api/clients/", json={"name": "Searchable Pagination Match Two"})
    client.post("/api/clients/", json={"name": "Totally Different Name"})

    resp = client.get("/api/clients/", params={"search": "Searchable Pagination", "limit": 10, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 2
    assert len(resp.json()) == 2


def test_overdue_only_filter_matches_the_exact_rule(client, test_user):
    """balance > 0 AND order_date more than 30 days ago - same rule the
    frontend previously computed client-side. Confirms an order with a
    balance but placed recently is excluded, an order fully paid but old
    is excluded, and only the genuinely overdue order is returned."""
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Overdue Filter Test Client"}).json()["id"]

    old_date = (datetime.utcnow() - timedelta(days=45)).isoformat()
    recent_date = (datetime.utcnow() - timedelta(days=5)).isoformat()

    genuinely_overdue = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": old_date, "order_value": "10000.00", "advance": "0",
    }).json()
    recent_with_balance = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": recent_date, "order_value": "10000.00", "advance": "0",
    }).json()
    old_but_paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": old_date, "order_value": "10000.00", "advance": "10000.00",
    }).json()

    resp = client.get("/api/orders/", params={"client_id": client_id, "overdue_only": True})
    result_ids = {o["id"] for o in resp.json()}
    assert genuinely_overdue["id"] in result_ids
    assert recent_with_balance["id"] not in result_ids
    assert old_but_paid["id"] not in result_ids


def test_overdue_only_composes_with_pagination(client, test_user):
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Overdue Pagination Test Client"}).json()["id"]
    old_date = (datetime.utcnow() - timedelta(days=60)).isoformat()

    for i in range(3):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": old_date, "order_value": "5000.00", "advance": "0",
        })

    resp = client.get("/api/orders/", params={"client_id": client_id, "overdue_only": True, "limit": 1, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 3
    assert len(resp.json()) == 1
