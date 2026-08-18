"""Tests for the real, event-driven notification system - every
notification here must trace back to an actual database condition, and
repeated checks must never spam duplicates."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_low_stock_material_generates_notification(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Low Stock Notif Material", "unit": "Sheets", "opening_stock": 2, "minimum_stock": 10,
    })
    resp = client.get("/api/notifications/")
    assert resp.status_code == 200
    matches = [n for n in resp.json() if n["title"] == "Low Stock Notif Material is running low"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "WARNING"
    assert matches[0]["notification_type"] == "LOW_STOCK"


def test_out_of_stock_material_generates_critical_notification(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Out Of Stock Notif Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    })
    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if "Out Of Stock Notif Material" in n["title"]]
    assert len(matches) == 1
    assert matches[0]["severity"] == "CRITICAL"
    assert matches[0]["notification_type"] == "OUT_OF_STOCK"


def test_checking_twice_does_not_create_duplicate_notifications(client, test_user):
    """The core requirement (Section 46) - repeated checks (e.g. opening
    the panel multiple times) must not spam the same situation."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Dedup Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    })
    client.get("/api/notifications/")
    client.get("/api/notifications/")
    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if "Dedup Test Material" in n["title"]]
    assert len(matches) == 1


def test_marking_read_allows_a_fresh_notification_later(client, test_user):
    """A resolved (read) notification shouldn't permanently block a new
    one if the same situation recurs - only unread duplicates are
    suppressed."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Reopen Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    }).json()

    first_check = client.get("/api/notifications/").json()
    notif = next(n for n in first_check if "Reopen Test Material" in n["title"])
    client.put(f"/api/notifications/{notif['id']}/read")

    second_check = client.get("/api/notifications/").json()
    matches = [n for n in second_check if "Reopen Test Material" in n["title"]]
    assert len(matches) == 2  # the read one, plus a fresh unread one
    assert sum(1 for m in matches if not m["is_read"]) == 1


def test_purchase_received_generates_success_notification(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Notif Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 100,
    }).json()

    client.post("/api/purchases/", json={
        "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if n["notification_type"] == "PURCHASE_RECEIVED"
               and "Purchase Notif Material" in n["title"]]
    assert len(matches) == 1
    assert matches[0]["severity"] == "SUCCESS"


def test_two_separate_purchases_of_the_same_material_both_notify(client, test_user):
    """Unlike stock-level notifications, purchases are genuinely
    distinct events each time - no dedup should collapse them."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Two Purchases Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Two Purchases Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 100,
    }).json()

    for _ in range(2):
        client.post("/api/purchases/", json={
            "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        })

    resp = client.get("/api/notifications/")
    matches = [n for n in resp.json() if n["notification_type"] == "PURCHASE_RECEIVED"
               and "Two Purchases Material" in n["title"]]
    assert len(matches) == 2


def test_unread_count_matches_actual_unread_notifications(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Unread Count Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    })
    all_notifs = client.get("/api/notifications/").json()
    expected_unread = sum(1 for n in all_notifs if not n["is_read"])

    resp = client.get("/api/notifications/unread-count")
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_unread


def test_mark_all_read_clears_unread_count(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Mark All Read Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    })
    client.get("/api/notifications/")
    client.put("/api/notifications/read-all")

    resp = client.get("/api/notifications/unread-count")
    assert resp.json()["count"] == 0


def test_notification_has_working_deep_link_path(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Deep Link Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 5,
    }).json()
    resp = client.get("/api/notifications/")
    match = next(n for n in resp.json() if "Deep Link Material" in n["title"])
    assert match["action_path"] == f"/materials/{material['id']}"
    assert match["related_entity_type"] == "material"
    assert match["related_entity_id"] == material["id"]
