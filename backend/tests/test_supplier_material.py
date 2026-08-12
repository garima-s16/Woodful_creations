"""Tests for the real Supplier <-> Material many-to-many (Section 7).
Distinct from Material.supplier_id (the existing single "primary
supplier" field, untouched here)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_link_supplier_to_material(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Supplier Material Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Supplier Material Test Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"],
        "supplier_sku": "SUP-SKU-001", "supplier_price": "1800.00", "moq": 10, "lead_time_days": 5,
    })
    assert resp.status_code == 201
    assert resp.json()["supplier_sku"] == "SUP-SKU-001"


def test_duplicate_supplier_material_pair_rejected(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Dup Pair Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Dup Pair Test Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    resp = client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    assert resp.status_code == 400


def test_material_can_have_multiple_suppliers(client, test_user):
    """The core many-to-many requirement - the same material linked to
    two different suppliers, each with their own price."""
    _login(client, test_user)
    supplier_a = client.post("/api/suppliers/", json={"name": "Multi Supplier A"}).json()
    supplier_b = client.post("/api/suppliers/", json={"name": "Multi Supplier B"}).json()
    material = client.post("/api/materials/", json={
        "name": "Multi Supplier Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()

    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_a["id"], "material_id": material["id"], "supplier_price": "1800.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_b["id"], "material_id": material["id"], "supplier_price": "1750.00",
    })

    resp = client.get(f"/api/supplier-materials/by-material/{material['id']}")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    supplier_names = {link["supplier_name"] for link in resp.json()}
    assert supplier_names == {"Multi Supplier A", "Multi Supplier B"}


def test_preferred_supplier_sorted_first(client, test_user):
    _login(client, test_user)
    cheap_supplier = client.post("/api/suppliers/", json={"name": "Cheap Non-Preferred Supplier"}).json()
    preferred_supplier = client.post("/api/suppliers/", json={"name": "Preferred Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Preferred Sort Test Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()

    client.post("/api/supplier-materials/", json={
        "supplier_id": cheap_supplier["id"], "material_id": material["id"], "supplier_price": "1000.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": preferred_supplier["id"], "material_id": material["id"],
        "supplier_price": "1500.00", "is_preferred": True,
    })

    resp = client.get(f"/api/supplier-materials/by-material/{material['id']}")
    results = resp.json()
    assert results[0]["supplier_name"] == "Preferred Supplier"


def test_supplier_can_supply_multiple_materials(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Multi Material Supplier"}).json()
    material_a = client.post("/api/materials/", json={
        "name": "Multi Material A", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    material_b = client.post("/api/materials/", json={
        "name": "Multi Material B", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()

    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material_a["id"]})
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material_b["id"]})

    resp = client.get(f"/api/supplier-materials/by-supplier/{supplier['id']}")
    assert len(resp.json()) == 2


def test_recording_a_purchase_updates_last_purchase_price(client, test_user):
    """The specific auto-update behavior - last_purchase_price must not
    be a field the user has to remember to maintain by hand."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Last Price Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Last Price Test Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    link = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "1800.00",
    }).json()
    assert link["last_purchase_price"] is None

    client.post("/api/purchases/", json={
        "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "1750.00", "gst_percent": "18", "payment_status": "Paid",
    })

    updated = client.get(f"/api/supplier-materials/by-material/{material['id']}").json()[0]
    assert float(updated["last_purchase_price"]) == 1750.0


def test_purchase_without_existing_link_does_not_create_one(client, test_user):
    """Deliberate scoping - recording a purchase from a supplier not yet
    linked to the material must not silently auto-create a link."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Unlinked Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Unlinked Purchase Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/purchases/", json={
        "date": "2026-08-13T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })
    assert resp.status_code == 201

    links = client.get(f"/api/supplier-materials/by-material/{material['id']}").json()
    assert links == []
