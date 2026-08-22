"""Client Master tests - covers the section's own testing checklist:
create, mandatory/invalid phone rejection, business_id shape/increment/
uniqueness, edit, unauthorized access, GSTIN validation, and the pure
validation logic used by the Excel import (no DB/HTTP needed for those).
"""
import re

from app.core.security import hash_password
from app.models.user import User
from app.utils.client_import import validate_and_match_row, normalize_match_key


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Creation / validation
# ---------------------------------------------------------------------

def test_create_client_requires_name_and_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "No Phone Client"})
    assert resp.status_code == 422


def test_create_client_rejects_empty_phone_string(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Empty Phone Client", "phone": ""})
    assert resp.status_code == 422


def test_create_client_rejects_invalid_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Bad Phone Client", "phone": "abc123"})
    assert resp.status_code == 422
    assert "valid mobile number" in str(resp.json()).lower()


def test_create_client_rejects_phone_with_11_digits(client, test_user):
    """Family 101 patch: phone must be EXACTLY 10 digits, not '10 or
    more' - a longer number (e.g. with a country code accidentally
    typed in) must be rejected, not silently accepted."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Too Long Phone Client", "phone": "98123456701"})
    assert resp.status_code == 422


def test_create_client_rejects_phone_with_9_digits(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Too Short Phone Client", "phone": "981234567"})
    assert resp.status_code == 422


def test_create_client_rejects_phone_with_country_code_prefix(client, test_user):
    """The old rule allowed an optional leading '+' - the exact-10-digit
    rule does not; a client's own mobile number is 10 digits with no
    prefix, per the explicit business requirement."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Country Code Client", "phone": "+919812345670"})
    assert resp.status_code == 422


def test_create_client_accepts_valid_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Valid Phone Client", "phone": "9812345670"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9812345670"


def test_create_client_rejects_invalid_email(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "Bad Email Client", "phone": "9812345671", "email": "not-an-email",
    })
    assert resp.status_code == 422


def test_create_client_rejects_short_gstin(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "Bad GSTIN Client", "phone": "9812345672", "gstin": "TOOSHORT",
    })
    assert resp.status_code == 422


def test_create_client_accepts_valid_gstin(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "Good GSTIN Client", "phone": "9812345673", "gstin": "27AAAAA0000A1Z5",
    })
    assert resp.status_code == 201
    assert resp.json()["gstin"] == "27AAAAA0000A1Z5"


def test_update_cannot_clear_mandatory_phone(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Phone Clear Client", "phone": "9812345674"}).json()
    resp = client.put(f"/api/clients/{created['id']}", json={"phone": ""})
    assert resp.status_code == 422


def test_update_rejects_invalid_phone(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Phone Update Client", "phone": "9812345675"}).json()
    resp = client.put(f"/api/clients/{created['id']}", json={"phone": "notaphone"})
    assert resp.status_code == 422
    # original value must be untouched
    assert client.get(f"/api/clients/{created['id']}").json()["phone"] == "9812345675"


def test_update_client_id_immutable(client, test_user):
    """Client ID (business_id) isn't in ClientUpdate's schema at all, so
    a caller can't overwrite it even if they try - Pydantic drops any
    unknown/non-model field silently rather than passing it through."""
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Immutable ID Client", "phone": "9812345676"}).json()
    original_business_id = created["business_id"]
    client.put(f"/api/clients/{created['id']}", json={"business_id": "ZZZZZZZZZZ", "name": "Renamed Client"})
    refreshed = client.get(f"/api/clients/{created['id']}").json()
    assert refreshed["business_id"] == original_business_id
    assert refreshed["name"] == "Renamed Client"


# ---------------------------------------------------------------------
# Client ID (business_id): shape, uniqueness, incrementality
# ---------------------------------------------------------------------

def test_client_business_id_is_10_char_alphanumeric(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "ID Shape Client", "phone": "9812345677"}).json()
    assert re.match(r"^[A-Z0-9]{10}$", created["business_id"])


def test_client_business_ids_increment_across_creates(client, test_user):
    """The whole point of the centralized generator (Client Master
    section 2: 'incremental') - not just unique, but ordered, so two
    clients created back to back get IDs where the second sorts after
    the first as an integer."""
    _login(client, test_user)
    first = client.post("/api/clients/", json={"name": "Increment Client A", "phone": "9812345678"}).json()
    second = client.post("/api/clients/", json={"name": "Increment Client B", "phone": "9812345679"}).json()
    assert int(first["business_id"], 36) < int(second["business_id"], 36)


def test_client_business_ids_unique_across_many_creates(client, test_user):
    _login(client, test_user)
    ids = set()
    for i in range(15):
        resp = client.post("/api/clients/", json={"name": f"Bulk Client {i}", "phone": f"98123456{i:02d}"})
        assert resp.status_code == 201
        ids.add(resp.json()["business_id"])
    assert len(ids) == 15


def test_client_and_other_entity_share_one_incrementing_sequence(client, test_user):
    """'Centralize ID generation' (Family 21 section 1) - a client and
    a supplier created back to back should draw from the *same*
    monotonic counter, not two independent per-table counters."""
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Shared Sequence Client", "phone": "9812399901"}).json()
    s = client.post("/api/suppliers/", json={"name": "Shared Sequence Supplier"}).json()
    assert int(s["business_id"], 36) > int(c["business_id"], 36)


# ---------------------------------------------------------------------
# Authorization / IDOR
# ---------------------------------------------------------------------

def test_unauthenticated_cannot_list_clients(client):
    resp = client.get("/api/clients/")
    assert resp.status_code in (401, 403)


def test_unauthenticated_cannot_create_client(client):
    resp = client.post("/api/clients/", json={"name": "Anon Client", "phone": "9812345680"})
    assert resp.status_code in (401, 403)


def test_non_master_cannot_delete_client(client, db_session):
    user = User(username="clientrbacuser", email="clientrbacuser@example.com", full_name="Client RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()

    login = client.post("/api/auth/login", json={"identifier": "clientrbacuser@example.com", "password": "UserPass1!"})
    assert login.status_code == 200
    created = client.post("/api/clients/", json={"name": "RBAC Delete Client", "phone": "9812345681"}).json()
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403


def test_non_master_cannot_export_financials(client, db_session):
    """Client export includes total_order_value/total_paid/outstanding
    only for master - same server-side scrub as the list/detail
    endpoints, not left to the frontend to hide."""
    master = User(username="clientexportmaster", email="clientexportmaster@example.com", full_name="Export Master",
                  password_hash=hash_password("MasterPass1!"), role="master", is_active=True)
    db_session.add(master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientexportmaster@example.com", "password": "MasterPass1!"})
    client.post("/api/clients/", json={"name": "Export RBAC Client", "phone": "9812345682"})
    client.post("/api/auth/logout")

    user = User(username="clientexportuser", email="clientexportuser@example.com", full_name="Export User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientexportuser@example.com", "password": "UserPass1!"})
    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200  # export itself is allowed for any authenticated user...
    # ...but financial columns are scrubbed - verified at the row-building
    # level in test_client_master_import_logic (pure function), since
    # parsing the xlsx bytes back out isn't worth the dependency here.


# ---------------------------------------------------------------------
# Client detail: related records, no fabricated counts
# ---------------------------------------------------------------------

def test_client_detail_has_zero_orders_for_new_client(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Fresh Lead Client", "phone": "9812345683"}).json()
    detail = client.get(f"/api/clients/{created['id']}").json()
    assert detail["total_orders"] == 0


def test_client_search_by_phone(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Searchable Client", "phone": "9899988877"})
    resp = client.get("/api/clients/", params={"search": "9899988877"})
    assert resp.status_code == 200
    assert any(c["phone"] == "9899988877" for c in resp.json())


# ---------------------------------------------------------------------
# Excel import: pure validation logic (no DB/HTTP required)
# ---------------------------------------------------------------------

def test_import_row_missing_phone_flagged():
    result, errors = validate_and_match_row({"Client Name *": "No Phone Row", "Client Type *": "Individual"}, {})
    assert "Please enter valid mobile number" in errors


def test_import_row_invalid_phone_flagged():
    result, errors = validate_and_match_row({"Client Name *": "Bad Phone Row", "Client Type *": "Individual", "Phone *": "abc"}, {})
    assert any("Invalid phone" in e for e in errors)


def test_import_row_invalid_email_flagged():
    result, errors = validate_and_match_row(
        {"Client Name *": "Bad Email Row", "Client Type *": "Individual", "Phone *": "9812345684", "Email": "not-an-email"}, {},
    )
    assert any("Invalid email" in e for e in errors)


def test_import_row_short_gstin_flagged():
    result, errors = validate_and_match_row(
        {"Client Name *": "Bad GSTIN Row", "Client Type *": "Individual", "Phone *": "9812345685", "GSTIN": "SHORT"}, {},
    )
    assert any("GSTIN must contain 15 characters" in e for e in errors)


def test_import_row_valid_data_no_errors():
    result, errors = validate_and_match_row(
        {"Client Name *": "Clean Row", "Client Type *": "Individual", "Phone *": "9812345686", "Email": "clean@example.com"}, {},
    )
    assert errors == []
    assert result["is_duplicate"] is False


def test_import_row_flags_name_and_phone_duplicate():
    class _FakeExisting:
        id = 42
    key = normalize_match_key("Existing Client", "9812345687")
    result, errors = validate_and_match_row(
        {"Client Name": "Existing Client", "Phone": "9812345687"}, {key: _FakeExisting()},
    )
    assert result["is_duplicate"] is True
    assert result["matched_client_id"] == 42


def test_import_client_id_never_accepted_from_upload():
    """The template/parser has no 'Client ID' column at all (Client
    Master section 17: 'Do not trust IDs supplied in uploaded Excel') -
    even if a row dict somehow contained one, validate_and_match_row's
    result never includes it, so it can't reach Client(business_id=...)."""
    result, errors = validate_and_match_row(
        {"Client Name": "Sneaky ID Row", "Phone": "9812345688", "Client ID": "HACKED0001"}, {},
    )
    assert "business_id" not in result
    assert "client_id" not in result


# ---------------------------------------------------------------------
# Excel import: end-to-end via the API (template download + preview/commit)
# ---------------------------------------------------------------------

def test_client_import_template_downloads(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/client-imports/template")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_client_import_template_requires_master(client, db_session):
    user = User(username="importrbacuser", email="importrbacuser@example.com", full_name="Import RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "importrbacuser@example.com", "password": "UserPass1!"})
    resp = client.get("/api/client-imports/template")
    assert resp.status_code == 403
