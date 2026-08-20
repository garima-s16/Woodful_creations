"""Tests for Family 5 (Inventory & Material Management): the new
"Return from Issue" adjustment type (traceable back to a specific
Issue, with a real over-return rejection - the concrete "do not allow
arbitrary quantity changes" safeguard), and the new replenishment-
requirements chatbot handler (honest shortfall arithmetic, never a
fabricated target)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_return_from_issue_increases_stock(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Return Test Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    issue = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "5", "unit": "Sheets",
    }).json()
    before = client.get(f"/api/materials/{material['id']}").json()["current_stock"]

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "2", "reason": "Unused sheets returned from site", "related_issue_id": issue["id"],
    })
    assert resp.status_code == 201

    after = client.get(f"/api/materials/{material['id']}").json()["current_stock"]
    assert float(after) == float(before) + 2


def test_cannot_return_more_than_was_issued(client, test_user):
    """The concrete anti-arbitrary-quantity rule - a return can never
    exceed what was actually issued."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Over Return Test Material", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "5",
    }).json()
    issue = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "3", "unit": "Sheets",
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "5", "reason": "Trying to return more than issued", "related_issue_id": issue["id"],
    })
    assert resp.status_code == 400
    assert "only" in resp.json()["detail"].lower()


def test_cannot_double_return_beyond_remaining(client, test_user):
    """Two separate, legitimate-looking returns against the same issue
    must not together exceed the issued quantity."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Double Return Test Material", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "5",
    }).json()
    issue = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "5", "unit": "Sheets",
    }).json()

    first = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "3", "reason": "First partial return", "related_issue_id": issue["id"],
    })
    assert first.status_code == 201

    second = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "3", "reason": "Second return exceeding what remains", "related_issue_id": issue["id"],
    })
    assert second.status_code == 400


def test_return_requires_an_issue_reference(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "No Issue Ref Test Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "2", "reason": "No issue referenced",
    })
    assert resp.status_code == 400


def test_return_must_be_for_the_same_material_as_the_issue(client, test_user):
    _login(client, test_user)
    material_a = client.post("/api/materials/", json={
        "name": "Return Mismatch Material A", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    material_b = client.post("/api/materials/", json={
        "name": "Return Mismatch Material B", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    issue = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material_a["id"], "quantity_issued": "5", "unit": "Sheets",
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material_b["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "2", "reason": "Wrong material for this issue", "related_issue_id": issue["id"],
    })
    assert resp.status_code == 400


def test_chatbot_replenishment_requirements(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Replenishment Test Material", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "10",
    })
    resp = client.post("/api/chat/", json={"message": "what needs reordering"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["label"] == "Replenishment Test Material" for r in data["records"])
    assert any("Need 8" in r["sublabel"] for r in data["records"] if r["label"] == "Replenishment Test Material")


def test_bare_reorder_word_still_uses_existing_low_stock_handler(client, test_user):
    """Regression guard - the new, more specific trigger must not
    swallow the pre-existing bare "reorder" phrasing."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Bare Reorder Test Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })
    resp = client.post("/api/chat/", json={"message": "show me the reorder alert"})
    assert resp.status_code == 200
    assert "minimum stock" in resp.json()["response"].lower()
