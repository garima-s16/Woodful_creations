"""Client recognition business rule tests: order intake with client_name
+ client_phone must reuse an existing client only when BOTH name and
phone match; otherwise it must create a new client. Mirrors the exact
three scenarios (plus normalization edge cases) from the source
business-rule document.
"""
import re
from app.modules.clients.matching import normalize_name, normalize_phone
from tests.helpers import _login


def _create_order(client, name, phone, order_value=50000):
    return client.post("/api/orders/", json={
        "client_name": name, "client_phone": phone,
        "order_date": "2026-07-01T00:00:00", "order_value": order_value,
    })


# ---------------------------------------------------------------------
# Pure normalization (no DB/HTTP needed)
# ---------------------------------------------------------------------

def test_normalize_name_trims_and_lowercases():
    assert normalize_name("  Garima  ") == "garima"
    assert normalize_name("GARIMA") == "garima"
    assert normalize_name("Garima") == "garima"


def test_normalize_phone_strips_formatting():
    assert normalize_phone("97578 84676") == "9757884676"
    assert normalize_phone("(97578)-84676") == "9757884676"
    assert normalize_phone("9757884676") == "9757884676"


def test_normalize_empty_values():
    assert normalize_name("") == ""
    assert normalize_name(None) == ""
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


# ---------------------------------------------------------------------
# TEST 1 - same name, same phone -> reuse client, new order
# ---------------------------------------------------------------------

def test_same_name_and_phone_reuses_client(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676", order_value=200000)
    assert first.status_code == 201
    first_client_id = first.json()["client_id"]
    first_order_id = first.json()["id"]

    second = _create_order(client, "Garima", "9757884676", order_value=50000)
    assert second.status_code == 201
    assert second.json()["client_id"] == first_client_id, "Same name+phone must reuse the existing client"
    assert second.json()["id"] != first_order_id, "Every order must get a new Order ID"
    assert second.json()["order_code"] != first.json()["order_code"]

    clients_list = client.get("/api/clients/", params={"search": "Garima"}).json()
    assert len([c for c in clients_list if c["name"] == "Garima"]) == 1, \
        "Reusing a client on the second order must not create a duplicate client record"


def test_original_order_unchanged_after_second_order(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676", order_value=200000)
    original_status = first.json()["project_status"]
    _create_order(client, "Garima", "9757884676", order_value=50000)
    refreshed_first = client.get(f"/api/orders/{first.json()['id']}").json()
    assert refreshed_first["project_status"] == original_status
    assert refreshed_first["order_value"] == first.json()["order_value"]


# ---------------------------------------------------------------------
# TEST 2 - same name, different phone -> new client
# ---------------------------------------------------------------------

def test_same_name_different_phone_creates_new_client(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "Garima", "8645788789")
    assert second.status_code == 201
    assert second.json()["client_id"] != first.json()["client_id"]


# ---------------------------------------------------------------------
# TEST 3 - same phone, different name -> new client (must not inherit)
# ---------------------------------------------------------------------

def test_same_phone_different_name_creates_new_client(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "Sanket", "9757884676")
    assert second.status_code == 201
    assert second.json()["client_id"] != first.json()["client_id"], \
        "A matching phone alone must never cause a different-named client to inherit the existing Client ID"


# ---------------------------------------------------------------------
# Full 3-scenario data integrity check, in one sequence
# ---------------------------------------------------------------------

def test_full_scenario_data_integrity(client, test_user):
    _login(client, test_user)
    clients_before = len(client.get("/api/clients/").json())

    r1a = _create_order(client, "Garima", "9757884676")  # baseline
    r1b = _create_order(client, "Garima", "9757884676")  # Test 1: reuse
    r2 = _create_order(client, "Garima", "8645788789")   # Test 2: new (name match only)
    r3 = _create_order(client, "Sanket", "9757884676")   # Test 3: new (phone match only)

    for r in (r1a, r1b, r2, r3):
        assert r.status_code == 201

    clients_after = len(client.get("/api/clients/").json())
    # r1a creates 1 new client; r1b reuses it (+0); r2 creates 1 (+1); r3 creates 1 (+1)
    assert clients_after - clients_before == 3

    order_ids = {r1a.json()["id"], r1b.json()["id"], r2.json()["id"], r3.json()["id"]}
    assert len(order_ids) == 4, "All order IDs must be unique"

    order_codes = {r1a.json()["order_code"], r1b.json()["order_code"], r2.json()["order_code"], r3.json()["order_code"]}
    assert len(order_codes) == 4

    assert r1a.json()["client_id"] == r1b.json()["client_id"]
    assert r2.json()["client_id"] != r1a.json()["client_id"]
    assert r3.json()["client_id"] != r1a.json()["client_id"]
    assert r2.json()["client_id"] != r3.json()["client_id"]


# ---------------------------------------------------------------------
# Negative / edge cases
# ---------------------------------------------------------------------

def test_whitespace_only_name_difference_still_matches(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "  Garima  ", "9757884676")
    assert second.json()["client_id"] == first.json()["client_id"]


def test_capitalization_difference_still_matches(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "GARIMA", "9757884676")
    assert second.json()["client_id"] == first.json()["client_id"]


def test_phone_formatting_differences_still_match(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "Garima", "(97578)-84676")
    assert second.json()["client_id"] == first.json()["client_id"]


def test_empty_client_name_rejected(client, test_user):
    _login(client, test_user)
    resp = _create_order(client, "", "9757884676")
    assert resp.status_code == 422


def test_empty_client_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = _create_order(client, "Garima", "")
    assert resp.status_code == 422


def test_invalid_phone_on_new_client_rejected(client, test_user):
    """A garbled phone can't match anything, so this must fall through
    to new-client creation - and new-client creation still enforces
    Client Master's own mandatory valid-phone rule.

    This was a confirmed gap: find_or_create_client constructs
    Client(...) directly via the ORM, bypassing the ClientCreate
    Pydantic schema (and its phone validator) entirely - there was no
    validation at all on this path until it was added explicitly."""
    _login(client, test_user)
    resp = _create_order(client, "Someone New", "not-a-phone")
    assert resp.status_code == 422
    assert "valid mobile number" in str(resp.json()).lower()


def test_wrong_length_phone_on_new_client_via_order_intake_rejected(client, test_user):
    """Same gap, but with a numeric value of the wrong length (12
    digits) rather than a non-numeric string - proves the exact-10-
    digit rule, not just 'must be numeric', is enforced on this path too."""
    _login(client, test_user)
    resp = _create_order(client, "Someone Else New", "981234567012")
    assert resp.status_code == 422


def test_order_requires_client_identification(client, test_user):
    """Neither client_id nor client_name+client_phone supplied."""
    _login(client, test_user)
    resp = client.post("/api/orders/", json={"order_date": "2026-07-01T00:00:00", "order_value": 1000})
    assert resp.status_code == 422


def test_existing_client_id_path_still_works(client, test_user):
    """The pre-existing client_id-based order creation path (used when
    an order is added from a Client's own detail page, where the client
    is already known) must be unaffected by the new recognition path."""
    _login(client, test_user)
    existing_client = client.post("/api/clients/", json={"name": "Direct Client", "phone": "9812399999"}).json()
    resp = client.post("/api/orders/", json={
        "client_id": existing_client["id"], "order_date": "2026-07-01T00:00:00", "order_value": 75000,
    })
    assert resp.status_code == 201
    assert resp.json()["client_id"] == existing_client["id"]


# ===========================================================================
# Duplicate-client detection (from the former CRM test segment)
# ===========================================================================
def test_duplicate_check_finds_substring_match(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Sanket Kumar", "phone": "9000010103"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Sanket"})
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Sanket Kumar" in names


def test_duplicate_check_does_not_flag_genuinely_different_names(client, test_user):
    """Regression guard for the false positive caught while building
    this - two genuinely different approved names must not collide."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Ashu", "phone": "9000010104"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Ishu"})
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Ashu" not in names


def test_duplicate_check_catches_typo_variant(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Sanket", "phone": "9000010105"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Sankett"})
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Sanket" in names


# ===========================================================================
# Client master regression checks (from the former estimates_orders segment)
# ===========================================================================
def test_client_master_creation_still_works(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Regression Check Client", "phone": "9812399988"})
    assert resp.status_code == 201
    assert re.match(r"^[A-Z0-9]{10}$", resp.json()["business_id"])


def test_client_master_recognition_still_works(client, test_user):
    _login(client, test_user)
    first = client.post("/api/orders/", json={
        "client_name": "Regression Recognition", "client_phone": "9812399977",
        "order_date": "2026-07-01T00:00:00", "order_value": "1000",
    })
    second = client.post("/api/orders/", json={
        "client_name": "Regression Recognition", "client_phone": "9812399977",
        "order_date": "2026-07-01T00:00:00", "order_value": "2000",
    })
    assert first.json()["client_id"] == second.json()["client_id"]
