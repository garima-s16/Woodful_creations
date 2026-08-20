"""Family 21 - Product Master: creation (standard + custom), 10-char
business_id, category/subcategory sync, bill-of-materials, cost-price
RBAC redaction, and delete guards once a product is referenced by an
order/estimate item."""
import re

from app.core.security import hash_password
from app.models.user import User

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee_user(client, db_session, name, username, email):
    employee = client.post("/api/employees/", json={
        "name": name, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def test_create_standard_product_gets_business_id_and_code(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/products/", json={
        "name": "Test Sliding Wardrobe", "product_type": "standard", "unit": "Piece",
        "cost_price": "40000", "selling_price": "55000",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["product_code"].startswith("PROD-")
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["is_active"] is True
    assert body["margin"] == 15000.0


def test_create_custom_product_no_sku_required(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/products/", json={
        "name": "Custom Test Mandir", "product_type": "custom", "unit": "Piece",
        "cost_price": "10000", "selling_price": "15000",
    })
    assert resp.status_code == 201
    assert resp.json()["product_type"] == "custom"


def test_invalid_product_type_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/products/", json={"name": "Bad Type Product", "product_type": "bogus"})
    assert resp.status_code == 422


def test_product_code_never_accepted_from_client_input(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/products/", json={
        "name": "Spoof Product Code", "product_code": "PROD-999", "business_id": "FAKE000001",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["product_code"] != "PROD-999"
    assert body["business_id"] != "FAKE000001"


def test_product_category_subcategory_sync(client, test_user):
    _login(client, test_user)
    category = client.post("/api/product-categories/", json={"name": "Test Seating"}).json()
    subcategory = client.post("/api/product-categories/subcategories", json={
        "category_id": category["id"], "name": "Test Chairs",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Dining Chair", "subcategory_id": subcategory["id"],
    }).json()
    assert product["category"] == "Test Seating"


def test_product_bom_creates_and_replaces_lines(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "BOM Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 2,
    }).json()
    product = client.post("/api/products/", json={
        "name": "BOM Test Product",
        "bom_items": [{"material_id": material["id"], "quantity": "2", "unit": "Sheets"}],
    }).json()
    assert len(product["bom_items"]) == 1
    assert product["bom_items"][0]["material_id"] == material["id"]

    updated = client.put(f"/api/products/{product['id']}", json={"bom_items": []}).json()
    assert updated["bom_items"] == []


def test_non_master_cannot_create_product(client, test_user, db_session):
    _login(client, test_user)
    _create_employee_user(client, db_session, "Product RBAC Employee", "productrbacuser", "productrbacuser@example.com")
    resp = client.post("/api/products/", json={"name": "Employee Attempt Product"})
    assert resp.status_code == 403


def test_non_master_read_has_cost_price_redacted(client, test_user, db_session):
    _login(client, test_user)
    product = client.post("/api/products/", json={
        "name": "Redaction Test Product", "cost_price": "1000", "selling_price": "2000",
    }).json()

    _create_employee_user(client, db_session, "Product Redaction Employee", "productredactuser", "productredactuser@example.com")
    resp = client.get(f"/api/products/{product['id']}").json()
    assert resp["cost_price"] is None
    assert resp["margin"] is None
    # Selling price is what a client is quoted, not internal cost data -
    # stays visible to every role.
    assert resp["selling_price"] == 2000.0


def test_master_read_sees_cost_price(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={
        "name": "Master Visibility Product", "cost_price": "1000", "selling_price": "2000",
    }).json()
    resp = client.get(f"/api/products/{product['id']}").json()
    assert resp["cost_price"] == 1000.0


def test_delete_product_used_on_order_item_is_blocked(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Order-Linked Product", "selling_price": "1000"}).json()
    client_row = client.post("/api/clients/", json={"name": "Product Delete Guard Client"}).json()
    client.post("/api/orders/", json={
        "client_id": client_row["id"], "order_date": "2026-08-01T00:00:00", "advance": "0",
        "items": [{"description": "Line", "quantity": "1", "rate": "1000", "product_id": product["id"]}],
    })
    resp = client.delete(f"/api/products/{product['id']}")
    assert resp.status_code == 400


def test_delete_unused_product_succeeds(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Deletable Product"}).json()
    resp = client.delete(f"/api/products/{product['id']}")
    assert resp.status_code == 204


def test_product_search_and_active_filter(client, test_user):
    _login(client, test_user)
    client.post("/api/products/", json={"name": "Searchable Unique Cabinet XYZ", "is_active": True})
    inactive = client.post("/api/products/", json={"name": "Inactive Cabinet XYZ"}).json()
    client.put(f"/api/products/{inactive['id']}", json={"is_active": False})

    resp = client.get("/api/products/", params={"search": "Unique Cabinet XYZ"})
    names = [p["name"] for p in resp.json()]
    assert "Searchable Unique Cabinet XYZ" in names

    resp = client.get("/api/products/", params={"active_only": True, "search": "Cabinet XYZ"})
    names = [p["name"] for p in resp.json()]
    assert "Inactive Cabinet XYZ" not in names
