"""Tests for "summarize material usage" - the last explicitly-named
Family 5 AI capability not yet built, and a regression guard for the
new "usage" trigger not colliding with plain stock queries."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_usage_summary(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Usage Summary Test Material", "unit": "Sheets", "opening_stock": "50", "minimum_stock": "10",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "5", "unit": "Sheets",
    })

    resp = client.post("/api/chat/", json={"message": "usage summary test material usage"})
    assert resp.status_code == 200
    data = resp.json()
    assert "5" in data["response"]
    assert any(r["label"] == "Usage Summary Test Material" for r in data["records"])


def test_material_usage_summary_via_summarize_phrasing(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "French Polish Laminate", "unit": "Sheets", "opening_stock": "30", "minimum_stock": "5",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "3", "unit": "Sheets",
    })

    resp = client.post("/api/chat/", json={"message": "summarize french polish laminate usage"})
    assert resp.status_code == 200
    assert "3" in resp.json()["response"]


def test_material_never_issued_reports_that_honestly(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Never Issued Test Material", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "never issued test material usage"})
    assert resp.status_code == 200
    assert "never been issued" in resp.json()["response"].lower()


def test_plain_stock_query_still_works_without_usage_word(client, test_user):
    """Regression guard - the new "usage" branch must not interfere
    with ordinary stock queries that don't mention usage."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Plain Stock Query Test Material", "unit": "Sheets", "opening_stock": "15", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "stock of plain stock query test material"})
    assert resp.status_code == 200
    assert "plain stock query test material" in resp.json()["response"].lower()
