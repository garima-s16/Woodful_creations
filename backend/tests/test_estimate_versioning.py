def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_client(client):
    resp = client.post("/api/clients/", json={"client_code": "CL-VER", "name": "Versioning Test Client", "phone": "9000010075"})
    return resp.json()["id"]


def test_revise_creates_new_version_not_overwrite(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)

    original = client.post("/api/estimates/", json={
        "estimate_code": "EST-VER-001", "client_id": client_id,
        "material_cost": "1000.00", "labor_cost": "500.00", "tax_percent": "18",
    })
    assert original.status_code == 201
    original_id = original.json()["id"]
    assert original.json()["version"] == 1

    revision = client.post(f"/api/estimates/{original_id}/revise")
    assert revision.status_code == 201
    assert revision.json()["version"] == 2
    assert revision.json()["parent_estimate_id"] == original_id
    assert revision.json()["id"] != original_id

    # original is untouched
    check_original = client.get(f"/api/estimates/{original_id}")
    assert check_original.json()["version"] == 1
    assert check_original.json()["material_cost"] == "1000.00"


def test_versions_endpoint_lists_full_chain(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)

    original = client.post("/api/estimates/", json={
        "estimate_code": "EST-VER-002", "client_id": client_id,
        "material_cost": "2000.00", "labor_cost": "800.00", "tax_percent": "18",
    })
    original_id = original.json()["id"]

    rev2 = client.post(f"/api/estimates/{original_id}/revise").json()
    client.post(f"/api/estimates/{rev2['id']}/revise")

    versions = client.get(f"/api/estimates/{original_id}/versions")
    assert versions.status_code == 200
    version_numbers = [v["version"] for v in versions.json()]
    assert version_numbers == [1, 2, 3]


def test_revise_nonexistent_estimate_404s(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/estimates/999999/revise")
    assert resp.status_code == 404
