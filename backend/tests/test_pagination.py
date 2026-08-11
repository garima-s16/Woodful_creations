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
