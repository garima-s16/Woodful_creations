"""Chatbot Product Master commands: search, create-proposal,
delete-proposal - Family 104 sections 8, 43-45. The chatbot never
writes to the database directly; every mutating action is a
ProposedAction the frontend executes via the same authorized REST
endpoint the UI uses.
"""
import re


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Static: chatbot never writes directly
# ---------------------------------------------------------------------

def test_chat_service_never_constructs_product_directly():
    import app.services.chat_service as chat_service
    import inspect
    source = inspect.getsource(chat_service)
    assert not re.search(r"\bProduct\s*\(", source)


# ---------------------------------------------------------------------
# Product search (read-only)
# ---------------------------------------------------------------------

def test_chatbot_finds_product_by_partial_name(client, test_user):
    _login(client, test_user)
    client.post("/api/products/", json={"name": "6 Seater Dining Table", "category": "Dining", "unit": "Piece"})
    resp = client.post("/api/chat/", json={"message": "find dining tables"})
    assert resp.status_code == 200
    assert "6 Seater Dining Table" in resp.json()["response"]


def test_chatbot_finds_product_by_code(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Chatbot Code Lookup Item", "unit": "Nos"}).json()
    resp = client.post("/api/chat/", json={"message": f"what is {product['product_code'].lower()}"})
    assert resp.status_code == 200
    assert "Chatbot Code Lookup Item" in resp.json()["response"]


def test_chatbot_unknown_product_code_reports_not_found(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "find prd-999999"})
    assert resp.status_code == 200
    assert "couldn't find" in resp.json()["response"].lower()


def test_chatbot_never_invents_product_search_results(client, test_user):
    """No products exist matching this term - the chatbot must say so,
    never fabricate a plausible-sounding result."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "find zzznonexistentproductxyz"})
    assert resp.status_code == 200
    assert "no products found" in resp.json()["response"].lower()


def test_product_search_broad_find_trigger_does_not_shadow_client_order_queries(client, test_user):
    """Regression: product search's 'find' trigger is intentionally
    broad (matches the spec's own 'find dining tables' example), which
    initially caused it to be dispatched BEFORE the more specific
    client-order query handler - "find Garima's order status" was
    being swallowed as a (fruitless) product search instead of ever
    reaching _route_client_order_query. Fixed by moving product search
    later in the dispatch chain, after every client/order/estimate-
    specific handler. This test doesn't assert a specific order exists
    (none does in this test's data) - it asserts the response is NOT
    the product-search "no products found" message, proving the
    client-order handler got first opportunity."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Dispatchorder", "phone": "9812399966"})
    resp = client.post("/api/chat/", json={"message": "find dispatchorder's order status"})
    assert resp.status_code == 200
    assert "no products found" not in resp.json()["response"].lower()


# ---------------------------------------------------------------------
# Product creation (proposal only, master-gated)
# ---------------------------------------------------------------------

def test_chatbot_proposes_product_creation_with_full_details(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={
        "message": "Add a new product called 6 Seater Dining Table, category Dining, unit Piece, rate 25000 and GST 18%.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is not None
    assert body["proposed_action"]["action_type"] == "create_product"
    payload = body["proposed_action"]["payload"]
    assert payload["name"] == "6 Seater Dining Table"
    assert payload["category"] == "Dining"
    assert payload["unit"] == "Piece"
    assert payload["selling_price"] == 25000.0
    assert payload["gst_percent"] == 18.0

    # Proposing never creates it - only confirming via the real API does.
    products = client.get("/api/products/", params={"search": "6 Seater Dining Table"}).json()
    assert len(products) == 0


def test_chatbot_product_creation_confirmed_via_real_api_matches_proposal(client, test_user):
    """End-to-end: the proposal's payload, when actually sent to the
    real POST /api/products/ endpoint (simulating what the frontend
    does on confirm), produces exactly the product that was proposed."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={
        "message": "Add a new product called Chatbot Confirmed Item, category Storage, unit Nos, rate 5000 and GST 12%.",
    })
    payload = resp.json()["proposed_action"]["payload"]
    created = client.post("/api/products/", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Chatbot Confirmed Item"
    assert body["category"] == "Storage"
    assert float(body["selling_price"]) == 5000.0
    assert re.match(r"^[A-Z0-9]{10}$", body["business_id"])


def test_chatbot_product_creation_requires_master(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    user = User(username="productchatbotrbacuser", email="productchatbotrbacuser@example.com",
                full_name="Product Chatbot RBAC User", password_hash=hash_password("UserPass1!"),
                role="user", is_active=True)
    db_session.add(user)
    db_session.commit()

    from app.models.product import Product
    products_before = db_session.query(Product).count()

    client.post("/api/auth/login", json={"identifier": "productchatbotrbacuser@example.com", "password": "UserPass1!"})
    resp = client.post("/api/chat/", json={"message": "Add a new product called RBAC Test Product"})
    assert resp.status_code == 200
    assert resp.json()["proposed_action"] is None
    assert "master account" in resp.json()["response"].lower()
    assert db_session.query(Product).count() == products_before


def test_chatbot_refuses_duplicate_product_creation(client, test_user):
    _login(client, test_user)
    client.post("/api/products/", json={"name": "Existing Chatbot Product", "unit": "Nos"})
    resp = client.post("/api/chat/", json={"message": "Add a new product called Existing Chatbot Product"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is None
    assert "already exists" in body["response"].lower()


# ---------------------------------------------------------------------
# Product deletion (proposal only, master-gated, historical-reference protected)
# ---------------------------------------------------------------------

def test_chatbot_deletion_requires_master(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    user = User(username="productdeletechatbotuser", email="productdeletechatbotuser@example.com",
                full_name="Product Delete Chatbot User", password_hash=hash_password("UserPass1!"),
                role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "productdeletechatbotuser@example.com", "password": "UserPass1!"})

    resp = client.post("/api/chat/", json={"message": "delete prd-001"})
    assert resp.status_code == 200
    assert resp.json()["proposed_action"] is None
    assert "do not have permission" in resp.json()["response"].lower()


def test_chatbot_proposes_deletion_of_unused_product(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Unused Chatbot Delete Product", "unit": "Nos"}).json()
    resp = client.post("/api/chat/", json={"message": f"delete {product['product_code'].lower()}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"]["action_type"] == "delete_product"
    assert body["proposed_action"]["payload"]["productId"] == product["id"]

    # confirming via the real API (what the frontend does) actually deletes it
    deleted = client.delete(f"/api/products/{product['id']}")
    assert deleted.status_code == 204


def test_chatbot_refuses_deletion_of_product_used_in_order(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Historically Used Chatbot Product", "unit": "Nos"}).json()
    c = client.post("/api/clients/", json={"name": "Chatbot Delete Test Client", "phone": "9812399955"}).json()
    client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Nos", "rate": "1000", "product_id": product["id"]}],
    })

    resp = client.post("/api/chat/", json={"message": f"delete {product['product_code'].lower()}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is None
    assert "deactivate" in body["response"].lower()


def test_chatbot_unknown_product_code_deletion_reports_not_found(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "delete prd-999999"})
    assert resp.status_code == 200
    assert resp.json()["proposed_action"] is None
    assert "couldn't find" in resp.json()["response"].lower()
