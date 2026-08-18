"""Tests for GSTIN validation (Section 9's own example: "GSTIN must
contain 15 characters") - enforced server-side, not just in the
frontend form, since the API can be called directly."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_short_gstin_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Test Supplier", "gstin": "TOOSHORT"})
    assert resp.status_code == 422


def test_valid_15_char_gstin_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Valid Supplier", "gstin": "27AAAAA0000A1Z5"})
    assert resp.status_code == 201
    assert resp.json()["gstin"] == "27AAAAA0000A1Z5"


def test_empty_gstin_allowed(client, test_user):
    """GSTIN is optional - not every supplier will have one recorded
    immediately."""
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Empty Supplier"})
    assert resp.status_code == 201


def test_update_also_validates_gstin(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "GSTIN Update Supplier"}).json()
    resp = client.put(f"/api/suppliers/{supplier['id']}", json={"gstin": "TOOSHORT"})
    assert resp.status_code == 422
