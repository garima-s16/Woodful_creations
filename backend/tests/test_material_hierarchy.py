"""Tests for the Category -> Subcategory -> Material -> dynamic
attributes foundation (Phase 1). Confirms the new hierarchy works AND
that existing flat-category material creation remains fully backward
compatible - nothing here should break a material created the old way."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_create_category_and_subcategory(client, test_user):
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Board & Wood Materials"}).json()
    assert len(category["business_id"]) == 10

    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Plywood",
    }).json()
    assert subcategory["category_id"] == category["id"]


def test_duplicate_category_name_rejected(client, test_user):
    _login(client, test_user)
    client.post("/api/material-categories/", json={"name": "Duplicate Category Test"})
    resp = client.post("/api/material-categories/", json={"name": "Duplicate Category Test"})
    assert resp.status_code == 400


def test_duplicate_subcategory_within_same_category_rejected(client, test_user):
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Dup Subcat Test Category"}).json()
    client.post("/api/material-categories/subcategories", json={"category_id": category["id"], "name": "Plywood"})
    resp = client.post("/api/material-categories/subcategories", json={"category_id": category["id"], "name": "Plywood"})
    assert resp.status_code == 400


def test_same_subcategory_name_allowed_under_different_categories(client, test_user):
    """"Hardware" under "Furniture Fittings" and "Hardware" under a
    different parent are genuinely different subcategories - the
    uniqueness is per-category, not global."""
    _login(client, test_user)
    cat_a = client.post("/api/material-categories/", json={"name": "Category A For Hardware Test"}).json()
    cat_b = client.post("/api/material-categories/", json={"name": "Category B For Hardware Test"}).json()
    resp_a = client.post("/api/material-categories/subcategories", json={"category_id": cat_a["id"], "name": "Hardware"})
    resp_b = client.post("/api/material-categories/subcategories", json={"category_id": cat_b["id"], "name": "Hardware"})
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


def test_attribute_definition_with_invalid_data_type_rejected(client, test_user):
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Attr Type Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Attr Type Test Subcategory",
    }).json()
    resp = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Thickness", "data_type": "not_a_real_type",
    })
    assert resp.status_code == 422


def test_material_created_with_subcategory_syncs_legacy_category_string(client, test_user):
    """The single most important compatibility guarantee: every existing
    consumer (dashboard, chatbot, PDF/Excel, low-stock filter) reads
    material.category as a plain string - this must stay populated and
    correct even for materials created through the new hierarchy."""
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Board & Wood Materials Sync Test"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "HDHMR Sync Test",
    }).json()

    material = client.post("/api/materials/", json={
        "name": "HDHMR 18mm Sync Test", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 5,
        "subcategory_id": subcategory["id"],
    }).json()
    assert material["category"] == "Board & Wood Materials Sync Test"
    assert material["subcategory_id"] == subcategory["id"]


def test_material_without_subcategory_still_works_the_old_way(client, test_user):
    """Backward compatibility - a material can still be created exactly
    the way it always was, with just a flat category string and no
    hierarchy at all."""
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Legacy Flat Category Material", "category": "Plywood", "unit": "Sheets",
        "opening_stock": 5, "minimum_stock": 2,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "Plywood"
    assert body["subcategory_id"] is None


def test_material_attribute_values_persist_with_correct_typed_storage(client, test_user):
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Attr Value Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Attr Value Test Subcategory",
    }).json()
    thickness_attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Thickness", "data_type": "number", "unit_label": "mm",
    }).json()
    brand_attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Brand", "data_type": "text",
    }).json()

    material = client.post("/api/materials/", json={
        "name": "Attr Value Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 2,
        "subcategory_id": subcategory["id"],
        "attribute_values": [
            {"attribute_definition_id": thickness_attr["id"], "value_number": "18"},
            {"attribute_definition_id": brand_attr["id"], "value_text": "Greenpanel"},
        ],
    }).json()
    values = {v["attribute_definition_id"]: v for v in material["attribute_values"]}
    assert float(values[thickness_attr["id"]]["value_number"]) == 18.0
    assert values[brand_attr["id"]]["value_text"] == "Greenpanel"
    assert "18" in values[thickness_attr["id"]]["display_value"] and "mm" in values[thickness_attr["id"]]["display_value"]


def test_updating_attribute_values_replaces_full_set(client, test_user):
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Update Attr Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Update Attr Test Subcategory",
    }).json()
    attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Colour", "data_type": "text",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Update Attr Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [{"attribute_definition_id": attr["id"], "value_text": "White"}],
    }).json()

    resp = client.put(f"/api/materials/{material['id']}", json={
        "attribute_values": [{"attribute_definition_id": attr["id"], "value_text": "Walnut"}],
    })
    assert resp.status_code == 200
    values = resp.json()["attribute_values"]
    assert len(values) == 1
    assert values[0]["value_text"] == "Walnut"


def test_attribute_value_returns_real_name_not_just_id(client, test_user):
    """Regression test - the API used to only return
    attribute_definition_id, forcing the frontend to show a raw
    internal ID ("Attribute #5") instead of an actual name."""
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Attr Name Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Attr Name Test Subcategory",
    }).json()
    attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Thickness", "data_type": "number", "unit_label": "mm",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Attr Name Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [{"attribute_definition_id": attr["id"], "value_number": "12"}],
    }).json()
    assert material["attribute_values"][0]["attribute_name"] == "Thickness"


def test_full_hierarchy_response_shape_matches_frontend_expectations(client, test_user):
    """Confirms GET /api/material-categories/ returns categories with
    nested subcategories with nested attribute_definitions - the exact
    shape MaterialAttributesEditor.jsx relies on to build its dropdowns."""
    _login(client, test_user)
    category = client.post("/api/material-categories/", json={"name": "Shape Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Shape Test Subcategory",
    }).json()
    client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Shape Test Attribute", "data_type": "text",
    })

    resp = client.get("/api/material-categories/")
    assert resp.status_code == 200
    found_category = next(c for c in resp.json() if c["id"] == category["id"])
    assert "subcategories" in found_category
    found_subcategory = next(s for s in found_category["subcategories"] if s["id"] == subcategory["id"])
    assert "attribute_definitions" in found_subcategory
    assert found_subcategory["attribute_definitions"][0]["name"] == "Shape Test Attribute"
