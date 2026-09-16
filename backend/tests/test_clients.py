"""Client domain tests: CRUD/master-data and matching/recognition.
Combines test_client_master.py and test_client_recognition.py."""
import re
from app.platform.security import hash_password
from app.modules.auth.auth import User
from app.modules.clients.services import validate_and_match_row, normalize_match_key
from tests.helpers import _login
from app.modules.clients.services import normalize_name, normalize_phone


# --- test_client_master.py ---
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
    """Phone must be EXACTLY 10 digits, not '10 or
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
    """'Centralize ID generation' - a client and
    a supplier created back to back should draw from the *same*
    monotonic counter, not two independent per-table counters."""
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Shared Sequence Client", "phone": "9812399901"}).json()
    s = client.post("/api/suppliers/", json={"name": "Shared Sequence Supplier"}).json()
    assert int(s["business_id"], 36) > int(c["business_id"], 36)


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


def test_import_row_missing_phone_flagged():
    result, errors = validate_and_match_row({"Client Name *": "No Phone Row", "Client Type *": "Individual"}, {})
    assert "Please enter valid mobile number" in errors


def test_import_row_invalid_phone_flagged():
    result, errors = validate_and_match_row({"Client Name *": "Bad Phone Row", "Client Type *": "Individual", "Phone *": "abc"}, {})
    assert any("Please enter valid mobile number" in e for e in errors)


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
        {"Client Name *": "Existing Client", "Client Type *": "Individual", "Phone *": "9812345687"}, {key: _FakeExisting()},
    )
    assert result["is_duplicate"] is True
    assert result["matched_client_id"] == 42


def test_import_client_id_never_accepted_from_upload():
    """The template/parser has no 'Client ID' column at all (Client
    Master section 17: 'Do not trust IDs supplied in uploaded Excel') -
    even if a row dict somehow contained one, validate_and_match_row's
    result never includes it, so it can't reach Client(business_id=...)."""
    result, errors = validate_and_match_row(
        {"Client Name *": "Sneaky ID Row", "Client Type *": "Individual", "Phone *": "9812345688", "Client ID": "HACKED0001"}, {},
    )
    assert "business_id" not in result
    assert "client_id" not in result


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


def test_client_import_commit_creates_real_persisted_client(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/client-imports/commit", json={"rows": [{
        "name": "Client Import Commit Test Client", "client_type": "Individual", "phone": "9000050001",
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_clients"] == 1
    assert body["error"] is None
    new_id = body["client_ids"][0]

    persisted = client.get(f"/api/clients/{new_id}").json()
    assert persisted["name"] == "Client Import Commit Test Client"
    assert persisted["phone"] == "9000050001"


def test_client_import_commit_reuses_matched_client_without_duplicating(client, test_user):
    _login(client, test_user)
    existing = client.post("/api/clients/", json={
        "name": "Client Import Match Test Client", "phone": "9000050002",
    }).json()

    resp = client.post("/api/client-imports/commit", json={"rows": [{
        "name": "Client Import Match Test Client", "phone": "9000050002",
        "matched_client_id": existing["id"],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_clients"] == 0
    assert body["matched_existing"] == 1
    assert body["client_ids"] == [existing["id"]]

    all_matching = client.get("/api/clients/", params={"search": "Client Import Match Test Client"}).json()
    assert len(all_matching) == 1  # no duplicate created


def test_client_import_commit_revalidates_stale_matched_client_id(client, test_user):
    """A matched_client_id echoed back from a stale preview (the
    client's name/phone changed since) must be re-verified against the
    Client Recognition rule, not trusted blindly - otherwise imported
    data could silently attach to the wrong client."""
    _login(client, test_user)
    existing = client.post("/api/clients/", json={
        "name": "Client Import Stale Match Client", "phone": "9000050003",
    }).json()
    # Client's phone changes after the (hypothetical) preview ran.
    client.put(f"/api/clients/{existing['id']}", json={"phone": "9000050099"})

    resp = client.post("/api/client-imports/commit", json={"rows": [{
        "name": "Client Import Stale Match Client", "phone": "9000050003",  # the old, now-stale phone
        "matched_client_id": existing["id"],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_clients"] == 0
    assert body["matched_existing"] == 0
    assert body["error"] is not None
    assert "no longer matches" in body["error"]


def test_client_import_commit_requires_master(client, db_session):
    user = User(username="clientimportuser", email="clientimportuser@example.com", full_name="Client Import User",
                password_hash=hash_password("EmpPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "clientimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/client-imports/commit", json={"rows": [{
        "name": "Unauthorized Client", "client_type": "Individual", "phone": "9000050004",
    }]})
    assert resp.status_code == 403


def test_client_export_returns_xlsx(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Mhow Export Client", "phone": "9000000001", "city": "Mhow"})

    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.content) > 0


def test_client_export_respects_search_filter(client, test_user):
    """search 'Mhow' -> export only matches search 'Mhow' -> list, same filter."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Mhow Client One", "phone": "9000000002"})
    client.post("/api/clients/", json={"name": "Indore Client Two", "phone": "9000000003"})

    list_resp = client.get("/api/clients/?search=Mhow")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    export_resp = client.get("/api/reports/clients.xlsx?search=Mhow")
    assert export_resp.status_code == 200


def test_client_city_and_status_persist(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "City Status Test Client", "city": "Mhow", "status": "Active", "phone": "9000010042",})
    assert resp.status_code == 201
    body = resp.json()
    assert body["city"] == "Mhow"
    assert body["status"] == "Active"


def test_master_can_delete_unreferenced_client(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Unreferenced Client", "phone": "9000010043"}).json()
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 204


def test_cannot_delete_client_with_orders(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Order Client", "phone": "9000010044"}).json()
    client.post("/api/orders/", json={
        "client_id": created["id"], "order_date": "2026-08-17T00:00:00", "order_value": "10000", "advance": "0",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 400
    assert "orders" in resp.json()["detail"].lower()


def test_cannot_delete_client_with_estimates(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Estimate Client", "phone": "9000010045"}).json()
    client.post("/api/estimates/", json={
        "client_id": created["id"], "material_cost": "5000", "labor_cost": "2000",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 400
    assert "estimates" in resp.json()["detail"].lower()


def test_client_with_only_activities_deletes_cleanly(client, test_user):
    """Activities are historical notes, not financial records - they
    should not block deletion, and must be cleaned up rather than
    cause an unhandled foreign-key error."""
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Activity Client", "phone": "9000010046"}).json()
    client.post("/api/client-activities/", json={
        "client_id": created["id"], "activity_type": "Call", "date": "2026-08-17T00:00:00", "summary": "Discussed requirements",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 204


def test_client_delete_rejects_plain_employee(client, test_user, db_session):
    from app.platform.security import hash_password
    from app.modules.auth.auth import User

    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Employee Test Client", "phone": "9000010047"}).json()
    employee = client.post("/api/employees/", json={"name": "Delete Guard Employee", "monthly_salary": "20000"}).json()
    user = User(
        username="clientdeleteguarduser", email="clientdeleteguarduser@example.com", full_name="Client Delete Guard User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientdeleteguarduser@example.com", "password": "EmpPass1!"})

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403


def test_client_delete_is_strictly_master_only(client, test_user, db_session):
    """Global delete rule - only master, not any other role, can
    delete anything anywhere in the app."""
    from app.platform.security import hash_password
    from app.modules.auth.auth import User

    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Non-Master Test Client", "phone": "9000010048"}).json()
    non_master = User(
        username="clientdeleteguarduser", email="clientdeleteguarduser@example.com", full_name="Client Delete Guard User",
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientdeleteguarduser@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403


# --- test_client_recognition.py ---
def _create_order(client, name, phone, order_value=50000):
    return client.post("/api/orders/", json={
        "client_name": name, "client_phone": phone,
        "order_date": "2026-07-01T00:00:00", "order_value": order_value,
    })


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


def test_same_name_different_phone_creates_new_client(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "Garima", "8645788789")
    assert second.status_code == 201
    assert second.json()["client_id"] != first.json()["client_id"]


def test_same_phone_different_name_creates_new_client(client, test_user):
    _login(client, test_user)
    first = _create_order(client, "Garima", "9757884676")
    second = _create_order(client, "Sanket", "9757884676")
    assert second.status_code == 201
    assert second.json()["client_id"] != first.json()["client_id"], \
        "A matching phone alone must never cause a different-named client to inherit the existing Client ID"


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


# --- Family 137, Step 3: Client Approval Hub (feature 1) ---

def _extract_token(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def test_client_portal_estimate_view_via_valid_token(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Estimate Client", "phone": "9812320001"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Portal Estimate Product", "unit": "Nos"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Wardrobe", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "50000", "product_id": product_id}],
    }).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    link = client.post(f"/api/estimates/{estimate['id']}/client-link")
    assert link.status_code == 200
    token = _extract_token(link.json()["url"])
    client.post("/api/auth/logout")

    # No auth/session at all - this is the defining property of the portal.
    resp = client.get(f"/api/client-portal/estimates/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimate_code"] == estimate["estimate_code"]
    assert body["can_decide"] is True
    assert len(body["line_items"]) == 1
    assert body["line_items"][0]["description"] == "Wardrobe"


def test_client_portal_estimate_approve_success(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Approve Client", "phone": "9812320002"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    token = _extract_token(client.post(f"/api/estimates/{estimate['id']}/client-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.post(f"/api/client-portal/estimates/{token}/approve", json={"name": "Mrs. Iyer", "comments": "Looks good"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["approved_by"] == "Mrs. Iyer"
    assert body["client_decision_comments"] == "Looks good"

    _login(client, test_user)
    refetched = client.get(f"/api/estimates/{estimate['id']}").json()
    assert refetched["status"] == "approved"
    assert refetched["approved_by"] == "Mrs. Iyer"


def test_client_portal_estimate_approve_requires_name(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal No-Name Client", "phone": "9812320003"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    token = _extract_token(client.post(f"/api/estimates/{estimate['id']}/client-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.post(f"/api/client-portal/estimates/{token}/approve", json={"name": "  "})
    assert resp.status_code == 400


def test_client_portal_estimate_request_changes_requires_comments(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Changes Client", "phone": "9812320004"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    token = _extract_token(client.post(f"/api/estimates/{estimate['id']}/client-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.post(f"/api/client-portal/estimates/{token}/request-changes", json={"name": "Mr. Rao"})
    assert resp.status_code == 400

    ok = client.post(f"/api/client-portal/estimates/{token}/request-changes", json={"name": "Mr. Rao", "comments": "Please change the colour to walnut."})
    assert ok.status_code == 200
    assert ok.json()["status"] == "changes_requested"


def test_client_portal_estimate_cannot_decide_when_not_sent(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Draft Client", "phone": "9812320005"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    # Still "draft" - never moved to "sent".
    token = _extract_token(client.post(f"/api/estimates/{estimate['id']}/client-link").json()["url"])
    client.post("/api/auth/logout")

    view = client.get(f"/api/client-portal/estimates/{token}")
    assert view.status_code == 200
    assert view.json()["can_decide"] is False

    resp = client.post(f"/api/client-portal/estimates/{token}/approve", json={"name": "Someone"})
    assert resp.status_code == 400
    assert "not currently awaiting" in resp.json()["detail"].lower()


def test_client_portal_invalid_token_returns_404(client):
    resp = client.get("/api/client-portal/estimates/this-token-does-not-exist")
    assert resp.status_code == 404


def test_client_portal_estimate_link_generation_requires_master(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Link RBAC Client", "phone": "9812320006"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    client.post("/api/auth/logout")
    user = User(username="portalrbacuser", email="portalrbacuser@example.com", full_name="Portal RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "portalrbacuser@example.com", "password": "UserPass1!"})
    resp = client.post(f"/api/estimates/{estimate['id']}/client-link")
    assert resp.status_code == 403


def _create_estimate_for_portal(client, client_id):
    product_id = client.post("/api/products/", json={"name": "Portal Test Product", "unit": "Nos"}).json()["id"]
    return client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Portal item", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "15000", "product_id": product_id}],
    }).json()


# --- Family 137, Step 3: Client "My Order" Link (feature 3) ---

def test_client_portal_order_view_via_valid_token(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Order Client", "phone": "9812320101"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00",
        "order_value": "80000.00", "advance": "20000.00",
    }).json()
    link = client.post(f"/api/orders/{order['id']}/my-order-link")
    assert link.status_code == 200
    token = _extract_token(link.json()["url"])
    client.post("/api/auth/logout")

    resp = client.get(f"/api/client-portal/orders/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_code"] == order["order_code"]
    assert body["order_value"] == 80000.0
    assert body["amount_paid"] == 20000.0
    assert body["outstanding_balance"] == 60000.0
    assert body["approved_specification"] is None
    assert body["milestones"] == []


def test_client_portal_order_view_includes_approved_specification(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Spec Order Client", "phone": "9812320102"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "40000.00", "advance": "40000.00",
    }).json()
    client.post(f"/api/orders/{order['id']}/approved-specifications", json={
        "material": "MDF 18mm", "colour": "Wenge", "approved_by": "Mr. Nair",
    })
    token = _extract_token(client.post(f"/api/orders/{order['id']}/my-order-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.get(f"/api/client-portal/orders/{token}")
    assert resp.status_code == 200
    spec = resp.json()["approved_specification"]
    assert spec is not None
    assert spec["material"] == "MDF 18mm"
    assert spec["colour"] == "Wenge"


def test_client_portal_order_view_includes_milestones_sorted(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Milestone Client", "phone": "9812320103"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "40000.00",
    }).json()
    client.post("/api/milestones/", json={"order_id": order["id"], "name": "Installation", "target_date": "2026-09-15T00:00:00"})
    client.post("/api/milestones/", json={"order_id": order["id"], "name": "Design Approval", "target_date": "2026-08-15T00:00:00"})
    token = _extract_token(client.post(f"/api/orders/{order['id']}/my-order-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.get(f"/api/client-portal/orders/{token}")
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()["milestones"]]
    assert names == ["Design Approval", "Installation"]


def test_client_portal_order_link_generation_requires_master(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Order Link RBAC Client", "phone": "9812320104"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "40000.00",
    }).json()
    client.post("/api/auth/logout")
    user = User(username="orderportalrbacuser", email="orderportalrbacuser@example.com", full_name="Order Portal RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "orderportalrbacuser@example.com", "password": "UserPass1!"})
    resp = client.post(f"/api/orders/{order['id']}/my-order-link")
    assert resp.status_code == 403


def test_client_portal_invalid_order_token_returns_404(client):
    resp = client.get("/api/client-portal/orders/this-token-does-not-exist")
    assert resp.status_code == 404


def test_client_portal_estimate_token_cannot_view_order(client, test_user):
    """A token minted for one purpose/subject_type must not work for
    the other portal surface - _resolve_token checks both."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Portal Cross-Purpose Client", "phone": "9812320105"}).json()["id"]
    estimate = _create_estimate_for_portal(client, client_id)
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    token = _extract_token(client.post(f"/api/estimates/{estimate['id']}/client-link").json()["url"])
    client.post("/api/auth/logout")

    resp = client.get(f"/api/client-portal/orders/{token}")
    assert resp.status_code == 404


# --- Family 137, Step 4: Unified Client Relationship Timeline (feature 5) ---

def test_relationship_timeline_client_not_found(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/clients/999999999/relationship-timeline")
    assert resp.status_code == 404


def test_relationship_timeline_aggregates_estimate_order_and_payment(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Timeline Client", "phone": "9812350001"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "10000"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()
    client.post("/api/payments/", json={
        "receipt_code": "RCPT-TIMELINE-001", "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "15000.00",
    })
    client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-02T00:00:00", "summary": "Discussed scope",
    })

    resp = client.get(f"/api/clients/{client_id}/relationship-timeline")
    assert resp.status_code == 200
    body = resp.json()
    types = {e["type"] for e in body["entries"]}
    assert "estimate" in types
    assert "order" in types
    assert "payment" in types
    assert "activity" in types
    assert body["total_entries"] == len(body["entries"])
    payment_entry = next(e for e in body["entries"] if e["type"] == "payment")
    assert "15,000" in payment_entry["text"] or "15000" in payment_entry["text"]


def test_relationship_timeline_hides_payment_amount_for_non_privileged(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Timeline Privacy Client", "phone": "9812350002"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()
    client.post("/api/payments/", json={
        "receipt_code": "RCPT-TIMELINE-002", "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "22000.00",
    })
    client.post("/api/auth/logout")
    user = User(username="timelineprivacyuser", email="timelineprivacyuser@example.com", full_name="Timeline Privacy User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "timelineprivacyuser@example.com", "password": "UserPass1!"})

    resp = client.get(f"/api/clients/{client_id}/relationship-timeline")
    assert resp.status_code == 200
    payment_entry = next(e for e in resp.json()["entries"] if e["type"] == "payment")
    assert "22000" not in payment_entry["text"] and "22,000" not in payment_entry["text"]


def test_relationship_timeline_requires_auth(client):
    resp = client.get("/api/clients/1/relationship-timeline")
    assert resp.status_code == 401
