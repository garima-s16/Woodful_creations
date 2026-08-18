"""Tests for the generic record_type/record_id context (Section 6/17's
"generic context architecture, not isolated IDs indefinitely"). Both
the new generic form and the old specific-field form must resolve to
the same answer - the refactor changed how context is interpreted
internally, not what it means."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_generic_record_type_and_id_resolves_material_context(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Generic Context Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 5,
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "Summarize this material",
        "context": {"record_type": "material", "record_id": material["id"]},
    })
    assert resp.status_code == 200
    assert "Generic Context Material" in resp.json()["response"]


def test_generic_and_specific_forms_give_identical_answers(client, test_user):
    """The refactor must not change what a question means - only how
    the context that answers it gets resolved internally."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Generic Vs Specific Supplier"}).json()

    generic_resp = client.post("/api/chat/", json={
        "message": "Tell me about this supplier",
        "context": {"record_type": "supplier", "record_id": supplier["id"]},
    })
    specific_resp = client.post("/api/chat/", json={
        "message": "Tell me about this supplier",
        "context": {"supplier_id": supplier["id"]},
    })
    assert generic_resp.json()["response"] == specific_resp.json()["response"]


def test_generic_form_takes_priority_when_both_are_sent(client, test_user):
    """If a caller somehow sends both forms with conflicting values, the
    generic form wins - it's the current, preferred representation."""
    _login(client, test_user)
    order_client_id = client.post("/api/clients/", json={"name": "Priority Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": order_client_id, "order_date": "2026-08-13T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    decoy_client = client.post("/api/clients/", json={"name": "Decoy Client"}).json()

    resp = client.post("/api/chat/", json={
        "message": "Summarize this order",
        "context": {"record_type": "order", "record_id": order["id"], "client_id": decoy_client["id"]},
    })
    assert order["order_code"] in resp.json()["response"]


def test_old_specific_field_context_still_works_unchanged(client, test_user):
    """Backward compatibility - existing frontend code (or anything not
    yet migrated to the generic form) must keep working exactly as
    before."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Backward Compat Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "Summarize this employee",
        "context": {"employee_id": employee["id"]},
    })
    assert resp.status_code == 200
    assert "Backward Compat Employee" in resp.json()["response"]
