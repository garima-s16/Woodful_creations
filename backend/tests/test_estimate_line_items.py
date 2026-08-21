def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _product(client, name):
    return client.post("/api/products/", json={"name": name, "unit": "Nos"}).json()["id"]


def test_estimate_with_multiple_line_items_computes_correct_totals(client, test_user):
    """The brief's own example figures - Wardrobe(2x85000) + Hardware(1x20000)
    + Installation(1x10000) = 200000 subtotal, with a 5000 discount and 18% GST."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Line Item Test Client", "phone": "9000010066"}).json()["id"]
    wardrobe_id = _product(client, "Wardrobe")
    hardware_id = _product(client, "Hardware")
    installation_id = _product(client, "Installation")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "discount": "5000.00", "tax_percent": "18",
        "line_items": [
            {"description": "Wardrobe", "category": "Furniture", "quantity": "2", "unit": "Nos", "rate": "85000.00", "product_id": wardrobe_id},
            {"description": "Hardware", "category": "Hardware", "quantity": "1", "unit": "Lot", "rate": "20000.00", "product_id": hardware_id},
            {"description": "Installation", "category": "Installation", "quantity": "1", "unit": "Lot", "rate": "10000.00", "product_id": installation_id},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["line_items"]) == 3
    assert body["line_items"][0]["amount"] == "170000.00"  # 2 * 85000, server-computed
    assert body["subtotal"] == "200000.00"
    assert body["tax_amount"] == "35100.00"  # (200000-5000) * 18% = 35100
    assert body["total_cost"] == "230100.00"  # 195000 + 35100


def test_line_item_amount_is_server_computed_not_trusted_from_client(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Trust Server Client", "phone": "9000010067"}).json()["id"]
    product_id = _product(client, "Test Item")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Test Item", "quantity": "3", "rate": "1000.00", "amount": "999999.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    # amount isn't even accepted on the input schema - server always computes qty*rate.
    assert resp.json()["line_items"][0]["amount"] == "3000.00"


def test_invalid_category_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Bad Category Client", "phone": "9000010068"}).json()["id"]
    product_id = _product(client, "Mystery Item")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Mystery Item", "category": "NotARealCategory", "quantity": "1", "rate": "500.00", "product_id": product_id}],
    })
    assert resp.status_code == 422


def test_estimate_with_no_line_items_falls_back_to_legacy_fields(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Legacy Fields Client", "phone": "9000010069"}).json()["id"]

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "100000.00", "labor_cost": "40000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["line_items"] == []
    assert body["subtotal"] == "140000.00"
    assert body["total_cost"] == "165200.00"


def test_updating_line_items_replaces_the_full_set_and_recomputes(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Update Line Items Client", "phone": "9000010070"}).json()["id"]
    original_id = _product(client, "Original Item")
    replacement_a_id = _product(client, "Replacement Item A")
    replacement_b_id = _product(client, "Replacement Item B")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Original Item", "quantity": "1", "rate": "10000.00", "product_id": original_id}],
    }).json()
    assert estimate["subtotal"] == "10000.00"

    resp = client.put(f"/api/estimates/{estimate['id']}", json={
        "line_items": [
            {"description": "Replacement Item A", "quantity": "2", "rate": "5000.00", "product_id": replacement_a_id},
            {"description": "Replacement Item B", "quantity": "1", "rate": "3000.00", "product_id": replacement_b_id},
        ],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["line_items"]) == 2
    assert body["subtotal"] == "13000.00"  # 10000 + 3000, not 10000+10000+3000
    assert not any(item["description"] == "Original Item" for item in body["line_items"])


def test_revision_copies_line_items_to_the_new_version(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Revision Line Items Client", "phone": "9000010071"}).json()["id"]
    product_id = _product(client, "Kitchen Unit")
    original = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Kitchen Unit", "quantity": "1", "rate": "150000.00", "product_id": product_id}],
    }).json()

    resp = client.post(f"/api/estimates/{original['id']}/revise")
    assert resp.status_code == 201
    revision = resp.json()
    assert revision["version"] == 2
    assert len(revision["line_items"]) == 1
    assert revision["line_items"][0]["description"] == "Kitchen Unit"
    assert revision["line_items"][0]["product_id"] == product_id  # Product ID preserved across revision
    assert revision["subtotal"] == "150000.00"


def test_estimate_still_gets_business_id_with_line_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Business ID Line Items Client", "phone": "9000010072"}).json()["id"]
    product_id = _product(client, "Item")
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Item", "quantity": "1", "rate": "1000.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    assert resp.json()["business_id"] is not None
    assert len(resp.json()["business_id"]) == 10


# ---------------------------------------------------------------------
# Product ID requirement (new): mandatory, validated, authoritative
# ---------------------------------------------------------------------

def test_line_item_without_product_id_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Product ID Client", "phone": "9000010073"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Freeform Item", "quantity": "1", "rate": "1000.00"}],
    })
    assert resp.status_code == 422
    assert "Product ID is required" in str(resp.json())


def test_line_item_with_invalid_product_id_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Invalid Product ID Client", "phone": "9000010074"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Fake Item", "quantity": "1", "rate": "1000.00", "product_id": 999999}],
    })
    assert resp.status_code == 400
    assert "Invalid Product ID" in str(resp.json())


def test_line_item_response_includes_product_name_from_master(client, test_user):
    """Product Name displayed must come from Product Master, not the
    freeform description the user typed."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Product Name Display Client", "phone": "9000010075"}).json()["id"]
    product = client.post("/api/products/", json={"name": "6 Seater Dining Table", "unit": "Nos"}).json()

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Dining table - client's own wording", "quantity": "1", "rate": "25000", "product_id": product["id"]}],
    })
    assert resp.status_code == 201
    assert resp.json()["line_items"][0]["product_name"] == "6 Seater Dining Table"


def test_inactive_product_cannot_be_used_in_new_estimate(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Inactive Product Client", "phone": "9000010076"}).json()["id"]
    product = client.post("/api/products/", json={"name": "Discontinued Item", "unit": "Nos"}).json()
    client.put(f"/api/products/{product['id']}", json={"is_active": False})

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Discontinued Item", "quantity": "1", "rate": "1000", "product_id": product["id"]}],
    })
    assert resp.status_code == 400
