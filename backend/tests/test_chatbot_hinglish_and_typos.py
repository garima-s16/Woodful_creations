"""Tests for broader Hinglish and typo coverage - specific, verified
gaps found by tracing the brief's own example phrases through the
actual parsing logic, not assumed working."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_stock_query_hinglish_kitna_hai(client, test_user):
    """"6mm hdhr kitna h" from the brief's own example - Hinglish
    phrasing with a typo, previously zero coverage existed."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR", "unit": "Sheets", "opening_stock": "12", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "6mm hdhr kitna h"})
    assert resp.status_code == 200
    assert "hdhmr" in resp.json()["response"].lower()
    assert "12" in resp.json()["response"]


def test_material_stock_query_bare_stock_prefix(client, test_user):
    """"stock hdhr" from the brief's own example."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR", "unit": "Sheets", "opening_stock": "8", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "stock hdhr"})
    assert "hdhmr" in resp.json()["response"].lower()


def test_bare_stock_query_does_not_misfire_on_generic_phrases(client, test_user):
    """"stock dashboard"/"stock report" must not claim it couldn't find
    a material named "dashboard" - a real risk caught while designing
    the new bare "stock X" pattern."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "stock dashboard"})
    assert "couldn't find a material" not in resp.json()["response"].lower()


def test_low_stock_query_hindi_kam_hai(client, test_user):
    """"material kam hai kya" from the brief's own example."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Low Stock Kam Hai Test Material", "unit": "Sheets",
        "opening_stock": "1", "minimum_stock": "10",
    })
    resp = client.post("/api/chat/", json={"message": "material kam hai kya"})
    assert "Low Stock Kam Hai Test Material" in [r["label"] for r in resp.json()["records"]]


def test_add_material_command_asks_for_clarification_when_no_name_given(client, test_user):
    """"add 4 sheet" from the brief's own example - a real bug traced
    and fixed: the description previously ended up as the bare word
    "sheet" (not empty), so the existing "I didn't catch what
    material" safeguard never actually caught this incomplete
    command, and would have proposed creating a material literally
    named "sheet"."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "add 4 sheet"})
    assert resp.json()["proposed_action"] is None
    assert "didn't catch" in resp.json()["response"].lower()


def test_add_material_command_still_works_with_real_material_name(client, test_user):
    """Regression guard - the clarification fix must not break the
    legitimate case where a real material name is present."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "add 5 hdhmr sheets"})
    assert resp.json()["proposed_action"] is not None
    assert "hdhmr" in resp.json()["proposed_action"]["payload"]["name"].lower()


def test_material_query_typo_tolerant_fallback(client, test_user):
    """Direct test of the fuzzy fallback itself - "hdhr" is genuinely
    not a substring of "HDHMR" (a letter is missing), which a plain
    ILIKE search can never bridge on its own."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "hdhr kitna hai"})
    assert "hdhmr" in resp.json()["response"].lower()
    assert "couldn't find" not in resp.json()["response"].lower()
