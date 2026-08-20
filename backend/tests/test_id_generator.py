"""Family 21 - centralized, atomic, incremental global ID generator.

generate_short_id() used to be a random secrets.choice() draw (Family
"business_id" work). It is now backed by a single atomically-
incremented counter (app/models/id_counter.py) - still exactly 10
uppercase alphanumeric characters (so every existing
test_business_id.py assertion still holds), but genuinely incremental
and shared across every entity type in the system."""
import re

from app.utils.id_generator import generate_short_id, _next_global_counter_value, _base36

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_generate_short_id_is_10_char_alphanumeric(db_session):
    value = generate_short_id(db_session)
    assert BUSINESS_ID_PATTERN.match(value), f"got {value!r}"


def test_generate_short_id_is_incremental(db_session):
    """Directly exercises the counter - each call must return a
    strictly greater underlying integer than the last, not merely a
    different random string."""
    first = generate_short_id(db_session)
    second = generate_short_id(db_session)
    third = generate_short_id(db_session)
    # base36 zero-padded strings compare lexicographically the same as
    # their numeric value for equal length, so this is a genuine
    # monotonic-increase check, not just "all different".
    assert first < second < third


def test_generate_short_id_never_collides_across_many_calls(db_session):
    values = {generate_short_id(db_session) for _ in range(200)}
    assert len(values) == 200


def test_counter_value_matches_base36_encoding(db_session):
    n = _next_global_counter_value(db_session)
    expected = _base36(n).upper().zfill(10)
    # The very next generated id must be exactly one more than n.
    next_id = generate_short_id(db_session)
    assert next_id == _base36(n + 1).upper().zfill(10)
    assert re.match(r"^[A-Z0-9]{10}$", expected)


def test_short_id_shared_across_different_entity_types(client, test_user, db_session):
    """"GLOBAL 10-CHARACTER IDs" - the same counter backs every entity
    type, so a client created immediately before a material must not
    reuse or collide with the material's id, and the two are drawn from
    one strictly increasing sequence rather than two independent ones."""
    _login(client, test_user)
    client_resp = client.post("/api/clients/", json={"name": "Global ID Sequence Client"}).json()
    material_resp = client.post("/api/materials/", json={
        "name": "Global ID Sequence Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
    }).json()
    assert client_resp["business_id"] != material_resp["business_id"]
    # Both drawn from the same monotonic sequence - the material (created
    # second) must have a strictly greater id than the client.
    assert material_resp["business_id"] > client_resp["business_id"]


def test_business_id_still_never_accepted_from_client_input(client, test_user):
    """Re-confirms the existing guarantee (test_business_id.py) still
    holds after the generation mechanism changed - a client-supplied
    business_id must still be silently ignored, never echoed back."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Spoof Test Client 2", "business_id": "ZZZZZZZZZZ"})
    assert resp.status_code == 201
    assert resp.json()["business_id"] != "ZZZZZZZZZZ"
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])
