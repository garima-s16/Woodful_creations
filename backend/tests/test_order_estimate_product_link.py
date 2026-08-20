"""Family 21 - Product <-> Order Item / Estimate Line Item
relationship: an order/estimate identifies exactly what was ordered/
quoted, a catalog Product's defaults fill in blanks, whatever the
caller explicitly sends still wins, and a genuinely custom line with no
Product Master entry still works exactly as before."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _make_product(client, **overrides):
    payload = {"name": "Link Test Wardrobe", "unit": "Piece", "selling_price": "50000"}
    payload.update(overrides)
    return client.post("/api/products/", json=payload).json()


def test_order_item_links_to_product(client, test_user):
    _login(client, test_user)
    product = _make_product(client)
    client_row = client.post("/api/clients/", json={"name": "Order Item Link Client"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "Wardrobe", "quantity": "1", "rate": "50000", "product_id": product["id"]}],
    }).json()
    assert order["items"][0]["product_id"] == product["id"]
    assert order["items"][0]["product_name"] == product["name"]


def test_order_item_defaults_from_product_when_blank(client, test_user):
    """description/unit/rate left blank on the item -> filled in from
    the Product Master's own catalog values."""
    _login(client, test_user)
    product = _make_product(client, name="Autofill Wardrobe", unit="Piece", selling_price="42000")
    client_row = client.post("/api/clients/", json={"name": "Order Item Autofill Client"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "", "quantity": "1", "rate": "0", "product_id": product["id"]}],
    }).json()
    item = order["items"][0]
    assert item["description"] == "Autofill Wardrobe"
    assert item["unit"] == "Piece"
    assert float(item["rate"]) == 42000.0
    assert float(item["amount"]) == 42000.0


def test_order_item_explicit_values_override_product_defaults(client, test_user):
    _login(client, test_user)
    product = _make_product(client, name="Override Wardrobe", selling_price="42000")
    client_row = client.post("/api/clients/", json={"name": "Order Item Override Client"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "Custom quoted price", "quantity": "1", "rate": "39999", "product_id": product["id"]}],
    }).json()
    item = order["items"][0]
    assert item["description"] == "Custom quoted price"
    assert float(item["rate"]) == 39999.0


def test_order_item_without_product_id_still_works(client, test_user):
    """A genuinely custom, one-off line never requires a Product Master
    entry - product_id stays null."""
    _login(client, test_user)
    client_row = client.post("/api/clients/", json={"name": "Order Item No Product Client"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "Miscellaneous service charge", "quantity": "1", "rate": "500"}],
    }).json()
    item = order["items"][0]
    assert item["product_id"] is None
    assert item["description"] == "Miscellaneous service charge"


def test_order_item_unknown_product_id_rejected(client, test_user):
    _login(client, test_user)
    client_row = client.post("/api/clients/", json={"name": "Order Item Bad Product Client"}).json()
    resp = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "x", "quantity": "1", "rate": "100", "product_id": 999999}],
    })
    assert resp.status_code == 404


def test_estimate_line_item_links_to_product_and_defaults(client, test_user):
    _login(client, test_user)
    product = _make_product(client, name="Estimate Link Wardrobe", selling_price="61000")
    client_row = client.post("/api/clients/", json={"name": "Estimate Item Link Client"}).json()
    estimate = client.post("/api/estimates/", json={
        "client_id": client_row["id"], "tax_percent": "18",
        "line_items": [{"description": "", "category": "Material", "quantity": "1", "rate": "0", "product_id": product["id"]}],
    }).json()
    item = estimate["line_items"][0]
    assert item["product_id"] == product["id"]
    assert item["description"] == "Estimate Link Wardrobe"
    assert float(item["rate"]) == 61000.0


def test_order_created_from_estimate_carries_product_link_forward(client, test_user):
    """When an order is created from an estimate, each OrderItem stays
    traceable to both the source estimate line AND the Product it
    represents - the Product trail must survive the conversion."""
    _login(client, test_user)
    product = _make_product(client, name="Conversion Wardrobe", selling_price="70000")
    client_row = client.post("/api/clients/", json={"name": "Estimate Conversion Client"}).json()
    estimate = client.post("/api/estimates/", json={
        "client_id": client_row["id"], "tax_percent": "18",
        "line_items": [{"description": "Conversion Wardrobe", "category": "Material",
                         "quantity": "1", "rate": "70000", "product_id": product["id"]}],
    }).json()
    order = client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "from_estimate_id": estimate["id"],
    }).json()
    assert order["items"][0]["product_id"] == product["id"]
