"""Tests for dynamic attribute-value filtering on the Material list
endpoint - the backend piece the Material Catalog filter fix depends on
(tracked in docs/UI_UX_BACKLOG.md, item 1)."""
import json


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _setup_plywood_subcategory(client):
    category = client.post("/api/material-categories/", json={"name": "Attr Filter Test Category"}).json()
    subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": category["id"], "name": "Attr Filter Test Plywood",
    }).json()
    thickness_attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Thickness", "data_type": "number", "unit_label": "mm",
    }).json()
    brand_attr = client.post(f"/api/material-categories/subcategories/{subcategory['id']}/attributes", json={
        "name": "Brand", "data_type": "text",
    }).json()
    return subcategory, thickness_attr, brand_attr


def test_filter_by_subcategory_id(client, test_user):
    _login(client, test_user)
    subcategory, _, _ = _setup_plywood_subcategory(client)
    client.post("/api/materials/", json={
        "name": "Subcat Filter Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
    })
    client.post("/api/materials/", json={
        "name": "Unrelated Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
    })

    resp = client.get("/api/materials/", params={"subcategory_id": subcategory["id"]})
    names = {m["name"] for m in resp.json()}
    assert "Subcat Filter Material" in names
    assert "Unrelated Material" not in names


def test_filter_by_single_numeric_attribute(client, test_user):
    _login(client, test_user)
    subcategory, thickness_attr, _ = _setup_plywood_subcategory(client)
    client.post("/api/materials/", json={
        "name": "18mm Filter Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [{"attribute_definition_id": thickness_attr["id"], "value_number": "18"}],
    })
    client.post("/api/materials/", json={
        "name": "12mm Filter Test Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [{"attribute_definition_id": thickness_attr["id"], "value_number": "12"}],
    })

    resp = client.get("/api/materials/", params={
        "attribute_filters": json.dumps({str(thickness_attr["id"]): "18"}),
    })
    names = {m["name"] for m in resp.json()}
    assert "18mm Filter Test Material" in names
    assert "12mm Filter Test Material" not in names


def test_multiple_attribute_filters_narrow_with_and_not_or(client, test_user):
    """The core correctness requirement - selecting both Thickness=18 AND
    Brand=Century must return only materials matching BOTH, not either."""
    _login(client, test_user)
    subcategory, thickness_attr, brand_attr = _setup_plywood_subcategory(client)

    matches_both = client.post("/api/materials/", json={
        "name": "Century 18mm Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [
            {"attribute_definition_id": thickness_attr["id"], "value_number": "18"},
            {"attribute_definition_id": brand_attr["id"], "value_text": "Century"},
        ],
    }).json()
    matches_thickness_only = client.post("/api/materials/", json={
        "name": "Greenpanel 18mm Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [
            {"attribute_definition_id": thickness_attr["id"], "value_number": "18"},
            {"attribute_definition_id": brand_attr["id"], "value_text": "Greenpanel"},
        ],
    }).json()

    resp = client.get("/api/materials/", params={
        "attribute_filters": json.dumps({str(thickness_attr["id"]): "18", str(brand_attr["id"]): "Century"}),
    })
    ids = {m["id"] for m in resp.json()}
    assert matches_both["id"] in ids
    assert matches_thickness_only["id"] not in ids


def test_invalid_attribute_filters_json_rejected(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/materials/", params={"attribute_filters": "not valid json"})
    assert resp.status_code == 400


def test_attribute_filter_composes_with_pagination(client, test_user):
    _login(client, test_user)
    subcategory, thickness_attr, _ = _setup_plywood_subcategory(client)
    for i in range(3):
        client.post("/api/materials/", json={
            "name": f"Pagination Attr Filter Material {i}", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
            "subcategory_id": subcategory["id"],
            "attribute_values": [{"attribute_definition_id": thickness_attr["id"], "value_number": "25"}],
        })

    resp = client.get("/api/materials/", params={
        "attribute_filters": json.dumps({str(thickness_attr["id"]): "25"}), "limit": 2, "offset": 0,
    })
    assert len(resp.json()) == 2
    assert int(resp.headers["X-Total-Count"]) == 3


def test_subcategory_and_attribute_filter_combine_correctly_like_the_catalog_ui(client, test_user):
    """Reproduces exactly what MaterialsPage.jsx's filter panel now
    sends: subcategory_id plus a JSON attribute_filters map together in
    one request - the real end-to-end shape, not just each independently."""
    _login(client, test_user)
    subcategory, thickness_attr, _ = _setup_plywood_subcategory(client)
    other_subcategory = client.post("/api/material-categories/subcategories", json={
        "category_id": subcategory["category_id"], "name": "Different Subcategory For UI Test",
    }).json()

    matching = client.post("/api/materials/", json={
        "name": "UI Filter Match", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": subcategory["id"],
        "attribute_values": [{"attribute_definition_id": thickness_attr["id"], "value_number": "18"}],
    }).json()
    # Same thickness value, but a different subcategory - must be excluded.
    client.post("/api/materials/", json={
        "name": "UI Filter Wrong Subcategory", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 1,
        "subcategory_id": other_subcategory["id"],
    })

    resp = client.get("/api/materials/", params={
        "subcategory_id": subcategory["id"],
        "attribute_filters": json.dumps({str(thickness_attr["id"]): "18"}),
    })
    names = {m["name"] for m in resp.json()}
    assert "UI Filter Match" in names
    assert "UI Filter Wrong Subcategory" not in names
