"""Tests for the flexible Location tree (Section 8) and the backward-
compatible sync into Material.location (the existing plain string
field every current consumer reads)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_create_top_level_location(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/locations/", json={"name": "Vijay Nagar Warehouse", "location_type": "Warehouse"})
    assert resp.status_code == 201
    assert resp.json()["full_path"] == "Vijay Nagar Warehouse"


def test_multi_level_full_path_builds_correctly(client, test_user):
    """The core requirement of the tree - a 3-level hierarchy producing
    the correct "Parent > Child > Grandchild" path."""
    _login(client, test_user)
    warehouse = client.post("/api/locations/", json={"name": "Main Warehouse", "location_type": "Warehouse"}).json()
    rack = client.post("/api/locations/", json={
        "name": "Rack A2", "location_type": "Rack", "parent_id": warehouse["id"],
    }).json()
    bin_ = client.post("/api/locations/", json={
        "name": "Bin H1", "location_type": "Bin", "parent_id": rack["id"],
    }).json()
    assert bin_["full_path"] == "Main Warehouse > Rack A2 > Bin H1"


def test_duplicate_name_under_same_parent_rejected(client, test_user):
    _login(client, test_user)
    warehouse = client.post("/api/locations/", json={"name": "Dup Location Test Warehouse"}).json()
    client.post("/api/locations/", json={"name": "Rack A1", "parent_id": warehouse["id"]})
    resp = client.post("/api/locations/", json={"name": "Rack A1", "parent_id": warehouse["id"]})
    assert resp.status_code == 400


def test_same_name_allowed_under_different_parents(client, test_user):
    """"Rack A1" in two different warehouses are genuinely different
    locations - uniqueness is per-parent, not global."""
    _login(client, test_user)
    warehouse_a = client.post("/api/locations/", json={"name": "Warehouse A For Rack Test"}).json()
    warehouse_b = client.post("/api/locations/", json={"name": "Warehouse B For Rack Test"}).json()
    resp_a = client.post("/api/locations/", json={"name": "Rack A1", "parent_id": warehouse_a["id"]})
    resp_b = client.post("/api/locations/", json={"name": "Rack A1", "parent_id": warehouse_b["id"]})
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


def test_material_created_with_location_id_syncs_legacy_location_string(client, test_user):
    """The core compatibility guarantee - material.location (plain
    string, read by every existing consumer) must reflect the real
    location's full path when location_id is set."""
    _login(client, test_user)
    warehouse = client.post("/api/locations/", json={"name": "Sync Test Warehouse"}).json()
    rack = client.post("/api/locations/", json={
        "name": "Sync Test Rack", "parent_id": warehouse["id"],
    }).json()

    material = client.post("/api/materials/", json={
        "name": "Location Sync Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
        "location_id": rack["id"],
    }).json()
    assert material["location"] == "Sync Test Warehouse > Sync Test Rack"
    assert material["location_id"] == rack["id"]


def test_material_without_location_id_still_works_the_old_way(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Legacy Flat Location Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "location": "Rack A1",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["location"] == "Rack A1"
    assert body["location_id"] is None


def test_get_children_of_a_parent_location(client, test_user):
    _login(client, test_user)
    warehouse = client.post("/api/locations/", json={"name": "Children Test Warehouse"}).json()
    client.post("/api/locations/", json={"name": "Rack A1", "parent_id": warehouse["id"]})
    client.post("/api/locations/", json={"name": "Rack A2", "parent_id": warehouse["id"]})

    resp = client.get("/api/locations/", params={"parent_id": warehouse["id"]})
    assert resp.status_code == 200
    names = {loc["name"] for loc in resp.json()}
    assert names == {"Rack A1", "Rack A2"}
