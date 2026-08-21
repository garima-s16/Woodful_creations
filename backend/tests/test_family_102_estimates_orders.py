"""Family 102 - Estimates & Orders. Covers what this family actually
added: server-side status-transition validation (previously any status
string could be set via blind mass-assignment), finalized-estimate
content protection, approved-only conversion eligibility, atomic
duplicate-conversion prevention, and AI/chat write-safety - mirroring
the Family 101 Client Master test structure and patterns.
"""
import re


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_client(client, name="Estimate Test Client", phone="9812300001"):
    return client.post("/api/clients/", json={"name": name, "phone": phone}).json()


def _create_estimate(client, client_id, **overrides):
    product_id = client.post("/api/products/", json={"name": "Test Product", "unit": "Nos"}).json()["id"]
    payload = {
        "client_id": client_id,
        "line_items": [{"description": "Test item", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "10000", "product_id": product_id}],
    }
    payload.update(overrides)
    return client.post("/api/estimates/", json=payload)


# ---------------------------------------------------------------------
# Estimate number generation
# ---------------------------------------------------------------------

def test_estimate_business_id_is_10_char_alphanumeric(client, test_user):
    _login(client, test_user)
    c = _create_client(client)
    est = _create_estimate(client, c["id"]).json()
    assert re.match(r"^[A-Z0-9]{10}$", est["business_id"])


def test_estimate_business_ids_increment(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300002")
    first = _create_estimate(client, c["id"]).json()
    second = _create_estimate(client, c["id"]).json()
    assert int(first["business_id"], 36) < int(second["business_id"], 36)


def test_estimate_code_never_client_supplied(client, test_user):
    """estimate_code is accepted in the payload (for schema
    compatibility) but always ignored - the server generates it."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300003")
    resp = _create_estimate(client, c["id"], estimate_code="HACKED-001")
    assert resp.status_code == 201
    assert resp.json()["estimate_code"] != "HACKED-001"


# ---------------------------------------------------------------------
# Server-side calculation
# ---------------------------------------------------------------------

def test_estimate_line_item_totals_computed_server_side(client, test_user):
    """Even if the client supplied a wrong 'amount', the server
    recomputes quantity * rate itself - line item schemas don't even
    accept an amount field from the caller."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300004")
    product_id = client.post("/api/products/", json={"name": "Item", "unit": "Nos"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": c["id"],
        "line_items": [{"description": "Item", "category": "Material", "quantity": "3", "unit": "Nos", "rate": "500", "product_id": product_id}],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["line_items"][0]["amount"]) == 1500.0


def test_estimate_line_item_negative_quantity_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300024")
    resp = client.post("/api/estimates/", json={
        "client_id": c["id"],
        "line_items": [{"description": "Item", "category": "Material", "quantity": "-1", "unit": "Nos", "rate": "500"}],
    })
    assert resp.status_code == 422


def test_estimate_line_item_zero_quantity_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300025")
    resp = client.post("/api/estimates/", json={
        "client_id": c["id"],
        "line_items": [{"description": "Item", "category": "Material", "quantity": "0", "unit": "Nos", "rate": "500"}],
    })
    assert resp.status_code == 422


def test_estimate_line_item_negative_rate_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300026")
    resp = client.post("/api/estimates/", json={
        "client_id": c["id"],
        "line_items": [{"description": "Item", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "-500"}],
    })
    assert resp.status_code == 422


def test_estimate_negative_discount_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300027")
    resp = _create_estimate(client, c["id"], discount="-100")
    assert resp.status_code == 422


def test_estimate_tax_percent_over_100_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300028")
    resp = _create_estimate(client, c["id"], tax_percent="150")
    assert resp.status_code == 422


def test_order_item_negative_quantity_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300029")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "category": "Material", "quantity": "-2", "unit": "Nos", "rate": "500"}],
    })
    assert resp.status_code == 422


def test_order_item_negative_rate_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300030")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "-500"}],
    })
    assert resp.status_code == 422


def test_order_item_unknown_product_id_rejected(client, test_user):
    """Family 102 Test 2: order line items must reference real Product
    Master rows, not just any integer - this was a confirmed gap."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300031")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Fake Product Item", "quantity": "1", "unit": "Nos", "rate": "1000", "product_id": 999999}],
    })
    assert resp.status_code == 400


def test_direct_order_with_two_real_products(client, test_user):
    """Family 102 Test 2, using the brief's own example figures:
    Product A qty=2 rate=1000, Product B qty=4 rate=750."""
    _login(client, test_user)
    product_a = client.post("/api/products/", json={"name": "Test Product A", "unit": "Nos"}).json()
    product_b = client.post("/api/products/", json={"name": "Test Product B", "unit": "Nos"}).json()
    c = _create_client(client, phone="9812300032")

    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [
            {"description": "Product A", "quantity": "2", "unit": "Nos", "rate": "1000", "product_id": product_a["id"]},
            {"description": "Product B", "quantity": "4", "unit": "Nos", "rate": "750", "product_id": product_b["id"]},
        ],
    })
    assert resp.status_code == 201
    order = resp.json()
    assert order["source_estimate_id"] is None  # direct order, no estimate

    items = order["items"]
    assert len(items) == 2
    item_a = next(i for i in items if i["product_id"] == product_a["id"])
    item_b = next(i for i in items if i["product_id"] == product_b["id"])
    assert float(item_a["amount"]) == 2000.0  # 2 * 1000
    assert float(item_b["amount"]) == 3000.0  # 4 * 750
    assert item_a["product_name"] == "Test Product A"
    assert item_b["product_name"] == "Test Product B"

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    refreshed_ids = {i["product_id"] for i in refreshed["items"]}
    assert refreshed_ids == {product_a["id"], product_b["id"]}


# ---------------------------------------------------------------------
# Status transitions - the core Family 102 fix
# ---------------------------------------------------------------------

def test_arbitrary_estimate_status_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300005")
    est = _create_estimate(client, c["id"]).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "not_a_real_status"})
    assert resp.status_code == 400


def test_draft_to_sent_allowed(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300006")
    est = _create_estimate(client, c["id"]).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_draft_can_go_directly_to_approved(client, test_user):
    """Matches established behavior (test_sales_estimate_conversion.py
    predates Family 102's status-transition rule and already exercises
    this path) - draft doesn't have to pass through 'sent' first."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300007")
    est = _create_estimate(client, c["id"]).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "approved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_rejected_is_terminal(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300008")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{est['id']}", json={"status": "rejected"})
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "approved"})
    assert resp.status_code == 400


def test_approved_can_be_cancelled(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300009")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{est['id']}", json={"status": "approved"})
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "cancelled"})
    assert resp.status_code == 200


def test_setting_status_to_its_own_value_is_a_noop_success(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300010")
    est = _create_estimate(client, c["id"]).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "draft", "remarks": "updated"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Finalized estimate content protection
# ---------------------------------------------------------------------

def test_finalized_estimate_content_edit_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300011")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{est['id']}", json={"status": "rejected"})
    resp = client.put(f"/api/estimates/{est['id']}", json={"material_cost": "99999"})
    assert resp.status_code == 400


def test_finalized_estimate_status_only_change_still_allowed(client, test_user):
    """A pure status transition (approved -> cancelled) must succeed
    even though the frontend's edit form always resubmits every field,
    including unchanged cost fields - only an actual VALUE change to a
    content field should be blocked, not its mere presence."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300012")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    approved = client.put(f"/api/estimates/{est['id']}", json={"status": "approved"}).json()
    # Resubmit the same material_cost/labor_cost/tax_percent unchanged,
    # alongside a legitimate status transition - must not be blocked.
    resp = client.put(f"/api/estimates/{est['id']}", json={
        "material_cost": str(approved["material_cost"]) if approved["material_cost"] is not None else "0",
        "labor_cost": str(approved["labor_cost"]) if approved["labor_cost"] is not None else "0",
        "tax_percent": "18", "status": "cancelled",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_finalized_estimate_line_items_edit_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300013")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{est['id']}", json={"status": "rejected"})
    product_id = client.post("/api/products/", json={"name": "New item", "unit": "Nos"}).json()["id"]
    resp = client.put(f"/api/estimates/{est['id']}", json={
        "line_items": [{"description": "New item", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "1", "product_id": product_id}],
    })
    assert resp.status_code == 400


def test_draft_estimate_content_edit_allowed(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300014")
    est = _create_estimate(client, c["id"]).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"material_cost": "5000"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Estimate -> Order conversion
# ---------------------------------------------------------------------

def _approve(client, estimate_id):
    client.put(f"/api/estimates/{estimate_id}", json={"status": "sent"})
    return client.put(f"/api/estimates/{estimate_id}", json={"status": "approved"}).json()


def test_conversion_requires_approved_status(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300015")
    est = _create_estimate(client, c["id"]).json()  # still draft
    resp = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert resp.status_code == 400


def test_conversion_of_rejected_estimate_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300016")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{est['id']}", json={"status": "rejected"})
    resp = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert resp.status_code == 400


def test_approved_estimate_converts_successfully(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300017")
    est = _create_estimate(client, c["id"]).json()
    approved = _approve(client, est["id"])
    resp = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert resp.status_code == 201
    order = resp.json()
    assert order["client_id"] == c["id"]
    assert len(order["items"]) == 1
    assert order["items"][0]["description"] == "Test item"

    refreshed_estimate = client.get(f"/api/estimates/{est['id']}").json()
    assert refreshed_estimate["order_id"] == order["id"]
    assert refreshed_estimate["status"] == "closed"


def test_estimate_manual_status_cannot_be_set_to_closed(client, test_user):
    """closed is system-only, set automatically by conversion - a
    direct PUT attempting it must be rejected, the same as any other
    unlisted transition target."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300033")
    est = _create_estimate(client, c["id"]).json()
    client.put(f"/api/estimates/{est['id']}", json={"status": "sent"})
    approved = client.put(f"/api/estimates/{est['id']}", json={"status": "approved"}).json()
    resp = client.put(f"/api/estimates/{est['id']}", json={"status": "closed"})
    assert resp.status_code == 400


def test_closed_estimate_cannot_be_converted_again(client, test_user):
    """Belt-and-suspenders on top of the order_id check: a closed
    estimate is also no longer 'approved', so conversion eligibility
    fails for a second, independent reason."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300034")
    est = _create_estimate(client, c["id"]).json()
    _approve(client, est["id"])
    client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    closed_estimate = client.get(f"/api/estimates/{est['id']}").json()
    assert closed_estimate["status"] == "closed"

    second_attempt = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert second_attempt.status_code == 400


def test_duplicate_conversion_prevented(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300018")
    est = _create_estimate(client, c["id"]).json()
    _approve(client, est["id"])
    first = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert first.status_code == 201
    second = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    })
    assert second.status_code == 400

    orders_for_client = client.get("/api/orders/", params={"client_id": c["id"]}).json()
    matching = [o for o in orders_for_client if o.get("id") == first.json()["id"]]
    assert len(matching) == 1


def test_conversion_preserves_client_relationship(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300019")
    est = _create_estimate(client, c["id"]).json()
    _approve(client, est["id"])
    order = client.post("/api/orders/", json={
        "from_estimate_id": est["id"], "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
    }).json()
    assert order["client_id"] == c["id"]


# ---------------------------------------------------------------------
# Order status validation
# ---------------------------------------------------------------------

def test_arbitrary_order_project_status_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300020")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Not A Real Stage"})
    assert resp.status_code == 400


def test_valid_order_project_status_accepted(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300021")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})
    assert resp.status_code == 200
    assert resp.json()["project_status"] == "Cancelled"


def test_arbitrary_order_sub_status_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300022")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    resp = client.put(f"/api/orders/{order['id']}", json={"design_status": "Nonsense"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------
# Security / RBAC
# ---------------------------------------------------------------------

def test_unauthenticated_cannot_create_estimate(client):
    resp = client.post("/api/estimates/", json={"client_id": 1})
    assert resp.status_code in (401, 403)


def test_non_master_cannot_create_estimate(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    user = User(username="estimaterbacuser", email="estimaterbacuser@example.com", full_name="Estimate RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "estimaterbacuser@example.com", "password": "UserPass1!"})
    resp = client.post("/api/estimates/", json={"client_id": 1})
    assert resp.status_code == 403


def test_non_master_cannot_change_order_status(client, test_user, db_session):
    _login(client, test_user)
    c = _create_client(client, phone="9812300023")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    client.post("/api/auth/logout")

    from app.core.security import hash_password
    from app.models.user import User
    user = User(username="orderrbacuser", email="orderrbacuser@example.com", full_name="Order RBAC User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "orderrbacuser@example.com", "password": "UserPass1!"})
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})
    assert resp.status_code == 403


def test_unauthorized_estimate_creation_client_must_exist(client, test_user):
    _login(client, test_user)
    resp = _create_estimate(client, client_id=999999999)
    assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------
# AI/chatbot cannot mutate estimates or orders
# ---------------------------------------------------------------------

def test_chat_service_never_constructs_estimate_or_order_rows():
    import app.services.chat_service as chat_service
    import app.services.agent_service as agent_service
    import inspect

    for module in (chat_service, agent_service):
        source = inspect.getsource(module)
        assert not re.search(r"\bEstimate\s*\(", source), f"{module.__name__} must never construct Estimate(...) directly"
        assert not re.search(r"\bOrder\s*\(", source), f"{module.__name__} must never construct Order(...) directly"
        for bad in ("create_estimate", "update_estimate", "delete_estimate", "accept_estimate",
                    "approve_estimate", "reject_estimate", "convert_estimate",
                    "create_order", "update_order", "delete_order", "cancel_order"):
            assert bad not in source, f"{module.__name__} must not contain {bad!r}"


def test_chat_service_never_proposes_estimate_or_order_write_action():
    import app.services.chat_service as chat_service
    import inspect

    source = inspect.getsource(chat_service)
    action_types = re.findall(r'action_type\s*=\s*"([^"]+)"', source)
    forbidden = {
        "create_estimate", "update_estimate", "delete_estimate", "accept_estimate", "approve_estimate",
        "reject_estimate", "convert_estimate", "create_order", "update_order", "delete_order", "cancel_order",
    }
    assert not (set(action_types) & forbidden)


# ---------------------------------------------------------------------
# Chatbot: order products query (Family 102 Test 6/7)
# ---------------------------------------------------------------------

def test_chatbot_reports_actual_products_in_order(client, test_user):
    """Test 6/7: chatbot must return the ACTUAL Order Items - real
    product names, not invented ones - and the response must match
    what the API itself returns for the same order."""
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Chatbot Test Sofa", "unit": "Nos"}).json()
    c = _create_client(client, phone="9812300035")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Sofa for living room", "quantity": "1", "unit": "Nos", "rate": "40000", "product_id": product["id"]}],
    }).json()

    resp = client.post("/api/chat/", json={"message": f"what products are in order {order['order_code']}"})
    assert resp.status_code == 200
    body = resp.json()
    assert order["order_code"] in body["response"]
    assert "Chatbot Test Sofa" in body["response"]
    # Cross-check against the real API response - must not diverge.
    api_order = client.get(f"/api/orders/{order['id']}").json()
    assert api_order["items"][0]["product_name"] == "Chatbot Test Sofa"


def test_chatbot_order_products_query_deictic_context(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "Deictic Test Table", "unit": "Nos"}).json()
    c = _create_client(client, phone="9812300036")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Table", "quantity": "1", "unit": "Nos", "rate": "15000", "product_id": product["id"]}],
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "what products are in this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    assert "Deictic Test Table" in resp.json()["response"]


def test_chatbot_order_products_hides_money_for_non_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "RBAC Test Chair", "unit": "Nos"}).json()
    c = _create_client(client, phone="9812300037")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Chair", "quantity": "1", "unit": "Nos", "rate": "12000", "product_id": product["id"]}],
    }).json()

    employee = client.post("/api/employees/", json={"name": "Order Products RBAC Employee"}).json()
    user = User(username="orderproductsrbacuser", email="orderproductsrbacuser@example.com",
                full_name="Order Products RBAC User", password_hash=hash_password("EmpPass1!"),
                role="user", employee_id=employee["id"], is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "orderproductsrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": f"what products are in order {order['order_code']}"})
    assert "Rs" not in resp.json()["response"]


# ---------------------------------------------------------------------
# AI/chatbot cannot mutate estimates or orders
# ---------------------------------------------------------------------

def test_chatbot_message_never_creates_estimate_or_order(client, test_user, db_session):
    from app.models.estimate import Estimate
    from app.models.order import Order

    _login(client, test_user)
    estimates_before = db_session.query(Estimate).count()
    orders_before = db_session.query(Order).count()

    for message in [
        "create an estimate for Garima 50000",
        "approve estimate EST-001",
        "create an order for Garima",
        "convert estimate to order",
    ]:
        resp = client.post("/api/chat/", json={"message": message})
        assert resp.status_code == 200
        body = resp.json()
        if body.get("proposed_action"):
            assert body["proposed_action"]["action_type"] not in (
                "create_estimate", "update_estimate", "accept_estimate", "create_order", "update_order",
            )

    assert db_session.query(Estimate).count() == estimates_before
    assert db_session.query(Order).count() == orders_before


# ---------------------------------------------------------------------
# Family 101 regression - Client Master must still work
# ---------------------------------------------------------------------

def test_family_101_client_creation_still_works(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Regression Check Client", "phone": "9812399988"})
    assert resp.status_code == 201
    assert re.match(r"^[A-Z0-9]{10}$", resp.json()["business_id"])


def test_family_101_client_recognition_still_works(client, test_user):
    _login(client, test_user)
    first = client.post("/api/orders/", json={
        "client_name": "Regression Recognition", "client_phone": "9812399977",
        "order_date": "2026-07-01T00:00:00", "order_value": "1000",
    })
    second = client.post("/api/orders/", json={
        "client_name": "Regression Recognition", "client_phone": "9812399977",
        "order_date": "2026-07-01T00:00:00", "order_value": "2000",
    })
    assert first.json()["client_id"] == second.json()["client_id"]
