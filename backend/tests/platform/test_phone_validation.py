"""Phone number validation: EXACTLY 10 digits, exact required message
'Please enter valid mobile number' for every rejection reason (missing,
wrong length, non-numeric, formatted, country-code-prefixed) - not a
different message per reason. Covers Client (mandatory), and the
Supplier/Employee gap (phone stays optional there, but must be valid
10 digits when given - previously unvalidated at all).
"""
from app.shared.validators import validate_phone
from tests.helpers import _login


EXACT_MESSAGE = "Please enter valid mobile number"


# ---------------------------------------------------------------------
# Pure function - the canonical rule, exactly 10 digits
# ---------------------------------------------------------------------

def test_validate_phone_exactly_10_digits_accepted():
    assert validate_phone("9876543210") is True


def test_validate_phone_9_digits_rejected():
    assert validate_phone("987654321") is False


def test_validate_phone_11_digits_rejected():
    assert validate_phone("98765432101") is False


def test_validate_phone_country_code_rejected():
    assert validate_phone("+919876543210") is False


def test_validate_phone_spaces_rejected():
    assert validate_phone("987 654 3210") is False


def test_validate_phone_separators_rejected():
    assert validate_phone("987-654-3210") is False


def test_validate_phone_alphabetic_rejected():
    assert validate_phone("abcdefghij") is False


def test_validate_phone_alphanumeric_rejected():
    assert validate_phone("98765432AB") is False


def test_validate_phone_empty_rejected():
    assert validate_phone("") is False


# ---------------------------------------------------------------------
# Client - every rejection reason uses the EXACT SAME message
# ---------------------------------------------------------------------

def test_client_missing_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "No Phone Client"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_wrong_length_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Wrong Length Client", "phone": "98765432101"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_non_numeric_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Non Numeric Client", "phone": "abcdefghij"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_alphanumeric_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Alphanumeric Client", "phone": "98765432AB"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_special_char_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Special Char Client", "phone": "98765-4321"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_country_code_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Country Code Client 2", "phone": "+919876543210"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_edit_invalid_phone_keeps_original_value(client, test_user):
    """Client Edit with invalid phone: request rejected, existing valid
    phone remains unchanged."""
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Edit Preserve Client", "phone": "9812345699"}).json()
    resp = client.put(f"/api/clients/{created['id']}", json={"phone": "12345"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())
    refreshed = client.get(f"/api/clients/{created['id']}").json()
    assert refreshed["phone"] == "9812345699"


def test_client_import_invalid_phone_row_rejected_exact_message(client, test_user):
    """Client Import with invalid phone: row rejected, exact error
    message shown, row not committed - via the pure validator used by
    the actual import route."""
    from app.modules.clients.import_utils import validate_and_match_row
    result, errors = validate_and_match_row({"Client Name *": "Bad Import Phone", "Client Type *": "Individual", "Phone *": "12345"}, {})
    assert EXACT_MESSAGE in errors


def test_client_import_missing_phone_row_exact_message():
    from app.modules.clients.import_utils import validate_and_match_row
    result, errors = validate_and_match_row({"Client Name *": "Missing Import Phone", "Client Type *": "Individual"}, {})
    assert EXACT_MESSAGE in errors


def test_direct_api_request_still_rejected_regardless_of_frontend(client, test_user):
    """Direct API request bypassing any frontend validation must still
    be rejected server-side - this IS that direct request."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Direct API Client", "phone": "notaphoneatall"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------
# Supplier - phone stays optional, but must be valid 10 digits if given
# (previously had ZERO format validation at all)
# ---------------------------------------------------------------------

def test_supplier_can_be_created_without_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "No Phone Supplier"})
    assert resp.status_code == 201


def test_supplier_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Bad Phone Supplier", "phone": "12345"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_supplier_valid_phone_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Good Phone Supplier", "phone": "9876543211"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543211"


def test_supplier_update_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    created = client.post("/api/suppliers/", json={"name": "Update Phone Supplier", "phone": "9876543212"}).json()
    resp = client.put(f"/api/suppliers/{created['id']}", json={"phone": "notaphone"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


# ---------------------------------------------------------------------
# Employee - phone stays optional, but must be valid 10 digits if given
# ---------------------------------------------------------------------

def test_employee_can_be_created_without_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "No Phone Employee"})
    assert resp.status_code == 201


def test_employee_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "Bad Phone Employee", "phone": "123"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_employee_valid_phone_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "Good Phone Employee", "phone": "9876543213"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543213"


def test_employee_update_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    created = client.post("/api/employees/", json={"name": "Update Phone Employee", "phone": "9876543214"}).json()
    resp = client.put(f"/api/employees/{created['id']}", json={"phone": "notaphone"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_employee_emergency_contact_stays_freeform(client, test_user):
    """emergency_contact is deliberately NOT subject to the strict
    10-digit rule (it may legitimately include a name/relation, e.g.
    'Wife - 9876543210'), unlike the employee's own phone field."""
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Emergency Contact Employee", "emergency_contact": "Wife - 9876543210",
    })
    assert resp.status_code == 201
    assert resp.json()["emergency_contact"] == "Wife - 9876543210"


# ---------------------------------------------------------------------
# Regression: estimate/order creation still works with
# valid phones, and existing seed-style client creation is unaffected
# ---------------------------------------------------------------------

def test_estimate_creation_still_works_after_phone_tightening(client, test_user):
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Estimate Regression Client", "phone": "9876543215"}).json()
    resp = client.post("/api/estimates/", json={"client_id": c["id"], "material_cost": "10000"})
    assert resp.status_code == 201


def test_order_creation_via_recognition_still_works_after_phone_tightening(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/orders/", json={
        "client_name": "Order Regression Client", "client_phone": "9876543216",
        "order_date": "2026-07-01T00:00:00", "order_value": "5000",
    })
    assert resp.status_code == 201
