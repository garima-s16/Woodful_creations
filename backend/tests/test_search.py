def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_search_requires_auth(client):
    resp = client.get("/api/search/", params={"q": "test"})
    assert resp.status_code == 401


def test_search_finds_client_by_name(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Zephyr Interiors"})

    resp = client.get("/api/search/", params={"q": "Zephyr"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["type"] == "Client" and r["label"] == "Zephyr Interiors" for r in results)


def test_search_finds_client_by_phone(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Phone Search Client", "phone": "9123456780"})

    resp = client.get("/api/search/", params={"q": "9123456780"})
    results = resp.json()
    assert any(r["type"] == "Client" and r["label"] == "Phone Search Client" for r in results)


def test_search_finds_material_by_code_not_just_name(client, test_user):
    _login(client, test_user)
    created = client.post("/api/materials/", json={
        "name": "Search Test Plywood", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 2,
    }).json()
    material_code = created["material_code"]

    resp = client.get("/api/search/", params={"q": material_code})
    results = resp.json()
    assert any(r["type"] == "Material" and r["id"] == created["id"] for r in results)


def test_search_returns_correct_navigable_path(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Path Check Client"}).json()

    resp = client.get("/api/search/", params={"q": "Path Check Client"})
    result = next(r for r in resp.json() if r["type"] == "Client")
    assert result["path"] == f"/clients/{created['id']}"


def test_search_across_multiple_types_returns_both(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "CrossType Alpha"})
    client.post("/api/suppliers/", json={"name": "CrossType Alpha Supplier"})

    resp = client.get("/api/search/", params={"q": "CrossType Alpha"})
    types_found = {r["type"] for r in resp.json()}
    assert "Client" in types_found
    assert "Supplier" in types_found


def test_search_empty_query_returns_empty_list(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/search/", params={"q": ""})
    assert resp.status_code in (200, 422)


def test_search_no_match_returns_empty_list(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/search/", params={"q": "ThisMatchesAbsolutelyNothingXYZ123"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_by_business_id_finds_the_record(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Business ID Search Client"}).json()
    business_id = created["business_id"]
    assert business_id is not None

    resp = client.get("/api/search/", params={"q": business_id})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["type"] == "Client" and r["id"] == created["id"] for r in results)


def test_search_by_business_id_across_entity_types(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Search By Business ID Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    resp = client.get("/api/search/", params={"q": material["business_id"]})
    results = resp.json()
    assert any(r["type"] == "Material" and r["id"] == material["id"] for r in results)
