from app.core.constants import MATERIAL_TYPES


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_types_have_thicknesses():
    for material, thicknesses in MATERIAL_TYPES.items():
        assert len(thicknesses) > 0


def test_get_material_types_endpoint(client):
    response = client.get("/api/inventory/materials")
    assert response.status_code == 200
    assert response.json()["materials"] == MATERIAL_TYPES


def test_inventory_list_requires_auth(client):
    response = client.get("/api/inventory/")
    assert response.status_code == 401


def _sample_material():
    material_type = next(iter(MATERIAL_TYPES))
    thickness = MATERIAL_TYPES[material_type][0]
    return material_type, thickness


def test_add_product_success(client, test_user):
    _login(client, test_user)
    material_type, thickness = _sample_material()

    response = client.post("/api/inventory/", json={
        "material_type": material_type,
        "thickness": thickness,
        "category": material_type,
        "quantity": 20,
        "min_quantity": 5,
        "price_per_unit": "150.50",
        "sku": "TEST-SKU-001",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["material_type"] == material_type
    assert body["quantity"] == 20


def test_add_product_rejects_invalid_material_type(client, test_user):
    _login(client, test_user)
    response = client.post("/api/inventory/", json={
        "material_type": "Not A Real Material",
        "thickness": 12,
        "category": "Bogus",
        "quantity": 1,
        "price_per_unit": "10.00",
    })
    assert response.status_code == 400


def test_add_product_rejects_invalid_thickness(client, test_user):
    _login(client, test_user)
    material_type, _ = _sample_material()
    response = client.post("/api/inventory/", json={
        "material_type": material_type,
        "thickness": 999,  # not one of the valid thicknesses for this material
        "category": material_type,
        "quantity": 1,
        "price_per_unit": "10.00",
    })
    assert response.status_code == 400


def test_inventory_list_after_add(client, test_user):
    _login(client, test_user)
    material_type, thickness = _sample_material()
    client.post("/api/inventory/", json={
        "material_type": material_type,
        "thickness": thickness,
        "category": material_type,
        "quantity": 5,
        "price_per_unit": "99.99",
        "sku": "TEST-SKU-002",
    })

    response = client.get("/api/inventory/")
    assert response.status_code == 200
    items = response.json()
    assert any(i["sku"] == "TEST-SKU-002" for i in items)
