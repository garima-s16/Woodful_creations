"""Tests for Sales - genuine gaps found in estimate-to-
order conversion (no status check existed at all, meaning a rejected
estimate could become an order, and re-converting an already-
converted estimate would silently orphan the first order's link),
plus estimates.xlsx export, pending-estimates chatbot handler, order/
estimate/invoice PDF exports, order balance recomputation, estimates-
export rate limiting, estimate versioning (revise creates a new
version rather than overwriting), estimate tax/total computation, and
the order-risk AI workspace (a persisted, re-redacted-on-read report
combining linked tasks/production jobs/materials issued)."""
import io
import re
from openpyxl import load_workbook
from tests.helpers import _login


def test_rejected_estimate_cannot_be_converted_to_order(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Conversion Test Rejected Client", "phone": "9000010171"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "10000"}).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "rejected"})

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "from_estimate_id": estimate["id"],
    })
    assert resp.status_code == 400
    assert "rejected" in resp.json()["detail"].lower()


def test_estimate_cannot_be_converted_twice(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Conversion Test Double Client", "phone": "9000010173"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "15000"}).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "approved"})
    first = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "from_estimate_id": estimate["id"],
    })
    assert first.status_code == 200

    second = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "from_estimate_id": estimate["id"],
    })
    assert second.status_code == 400
    assert "already" in second.json()["detail"].lower()


def test_estimates_export_requires_master(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Estimates Export Permission Employee"}).json()
    user = User(
        username="estimatesexportuser", email="estimatesexportuser@example.com",
        full_name="Estimates Export User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "estimatesexportuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/reports/estimates.xlsx")
    assert resp.status_code == 403


def test_estimates_export_works_for_master(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimates Export Master Client", "phone": "9000010174"}).json()["id"]
    client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "5000"})

    resp = client.get("/api/reports/estimates.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Estimates" in wb.sheetnames


def test_chatbot_pending_estimates(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chatbot Pending Estimate Client", "phone": "9000010175"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "8000"}).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})

    resp = client.post("/api/chat/", json={"message": "show pending estimates"})
    assert resp.status_code == 200
    assert estimate["estimate_code"] in resp.json()["response"] or any(
        r["label"] == estimate["estimate_code"] for r in resp.json()["records"]
    )

# ===========================================================================
# Estimate/order validation, status transitions, and RBAC (from the former estimates_orders segment)
# ===========================================================================
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
    """Order line items must reference real Product
    Master rows, not just any integer - this was a confirmed gap."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300031")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Fake Product Item", "quantity": "1", "unit": "Nos", "rate": "1000", "product_id": 999999}],
    })
    assert resp.status_code == 400


def test_direct_order_with_two_real_products(client, test_user):
    """Using the brief's own example figures:
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
# Status transitions - the core status-validation fix
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
    """Matches established behavior (this file's own earlier tests
    predates the status-transition rule and already exercises
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


def test_order_health_endpoint_on_track(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300026")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "ON_TRACK"
    assert body["order_code"] == order["order_code"]
    assert "pending_payment" in body  # master sees financial data


def test_order_health_endpoint_at_risk_and_employee_redaction(client, test_user, db_session):
    _login(client, test_user)
    c = _create_client(client, phone="9812300027")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "2000",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Health Endpoint Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Fit hardware", "status": "BLOCKED", "delay_reason": "Waiting for hinges",
    })
    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "AT_RISK"
    assert any("hinges" in r for r in body["reasons"])
    assert "pending_payment" in body

    client.post("/api/auth/logout")
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(username="healthendpointuser", email="healthendpointuser@example.com", full_name="Health Endpoint User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "healthendpointuser@example.com", "password": "UserPass1!"})
    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    assert "pending_payment" not in resp.json()


def test_order_health_endpoint_not_found(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/orders/999999999/health")
    assert resp.status_code == 404


def test_order_health_overdue_task_is_a_finding(client, test_user):
    """Regression: an open task past its due_date is a real signal
    (DailyTask.due_date is genuine data) and must not be invisible just
    because nobody marked it BLOCKED (Family 130 P0.1 s.3)."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300028")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Overdue Task Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Deliver hardware", "status": "TO DO",
        "due_date": "2020-01-01T00:00:00",
    })
    resp = client.get(f"/api/orders/{order['id']}/health")
    body = resp.json()
    assert body["risk_level"] == "AT_RISK"
    assert any("overdue" in r.lower() for r in body["reasons"])
    assert body["next_action"]["type"] == "overdue_task"


def test_order_health_production_blocker_is_a_finding(client, test_user):
    """Regression: a ProductionJob with a blocker_reason is a genuine
    production blocker even though it has no dedicated 'Blocked' status,
    and must outrank a plain overdue task in Next Action (s.5 priority)."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300029")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    client.post("/api/production-jobs/", json={
        "date": "2026-07-01T00:00:00", "order_id": order["id"], "operation": "Cutting",
        "status": "In Progress", "blocker_reason": "Waiting for CNC machine repair",
    })
    resp = client.get(f"/api/orders/{order['id']}/health")
    body = resp.json()
    assert body["risk_level"] == "AT_RISK"
    assert any("cnc" in r.lower() for r in body["reasons"])
    assert body["next_action"]["type"] == "production_blocker"
    assert body["readiness"]["production"] == "blocked"


def test_order_health_next_action_priority_blocked_task_over_shortage(client, test_user):
    """A blocked task must win Next Action over a material shortage
    even when both are present (s.5 priority order)."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300030")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Priority Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Fit hardware", "status": "BLOCKED", "delay_reason": "Waiting for hinges",
    })
    resp = client.get(f"/api/orders/{order['id']}/health")
    body = resp.json()
    assert body["next_action"]["type"] == "blocked_task"


def test_order_health_no_findings_uses_uncheckable_language(client, test_user):
    """Section 3: a clean result must say a blocker was not found from
    available data, not claim there is definitively 'no risk'."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300031")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    resp = client.get(f"/api/orders/{order['id']}/health")
    body = resp.json()
    assert "no blocker found" in body["reasons"][0].lower()
    assert body["next_action"] is None or body["next_action"]["type"] == "open_task"


def test_order_health_actual_completion_date_from_audit_log(client, test_user):
    """Section 7: actual completion is derived from the existing
    project_status audit trail, not a new column and not fabricated."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300032")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.json()["actual_completion_date"] is None
    assert resp.json()["readiness"]["delivery"] == "unavailable"

    client.put(f"/api/orders/{order['id']}", json={"project_status": "Completed"})
    resp = client.get(f"/api/orders/{order['id']}/health")
    body = resp.json()
    assert body["actual_completion_date"] is not None
    assert body["readiness"]["delivery"] == "delivered"


def test_order_list_needs_attention_flag_from_blocked_task(client, test_user):
    """Section 11: the Order List's needs_attention flag must come from
    the server's batched signals, not be silently absent or computed
    client-side."""
    _login(client, test_user)
    c = _create_client(client, phone="9812300033")
    quiet_order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "List Flag Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Fit hardware", "status": "BLOCKED", "delay_reason": "Waiting for hinges",
    })
    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    by_id = {o["id"]: o for o in resp.json()}
    assert by_id[order["id"]]["needs_attention"] is True
    assert "hinges" not in (by_id[order["id"]]["attention_reason"] or "")  # names the task, not the delay text
    assert by_id[quiet_order["id"]]["needs_attention"] is False


def test_order_list_shows_critical_risk_level_for_overdue_blocked_order(client, test_user):
    """P0.50 section 19/22 - the Orders List must distinguish CRITICAL
    severity, not just a flat needs_attention flag, using the same
    bounded, batched calculation as before (no new per-order query)."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    c = _create_client(client, phone="9812300034")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "List Critical Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Overdue delivery work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    by_id = {o["id"]: o for o in resp.json()}
    assert by_id[order["id"]]["attention_risk_level"] == "CRITICAL"


def test_order_list_sort_by_risk_surfaces_critical_order_first(client, test_user):
    """P0.50 section 19 - a CRITICAL order must surface first when
    sort=risk is requested, even though it was created before (and so
    would sort last under the default order_date-desc ordering) an
    on-track order created after it."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    c = _create_client(client, phone="9812300035")
    critical_order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-06-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Sort Risk Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-06-01T00:00:00", "employee_id": employee["id"], "order_id": critical_order["id"],
        "task_description": "Overdue critical sort work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })
    quiet_order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-08-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()

    # Default order: newest first - the quiet order (created later) is
    # expected to lead, confirming the base case still works correctly.
    default_resp = client.get("/api/orders/")
    assert default_resp.status_code == 200
    default_ids = [o["id"] for o in default_resp.json()]
    assert default_ids.index(quiet_order["id"]) < default_ids.index(critical_order["id"])

    # Risk sort: the CRITICAL order must now lead, regardless of date.
    risk_resp = client.get("/api/orders/", params={"sort": "risk"})
    assert risk_resp.status_code == 200
    risk_ids = [o["id"] for o in risk_resp.json()]
    assert risk_ids.index(critical_order["id"]) < risk_ids.index(quiet_order["id"])
    top = next(o for o in risk_resp.json() if o["id"] == critical_order["id"])
    assert top["attention_risk_level"] == "CRITICAL"


def test_order_invalid_priority_rejected(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300028")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
        "priority": "Critical",
    })
    assert resp.status_code == 422


def test_order_valid_priority_accepted(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300029")
    resp = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
        "priority": "Urgent",
    })
    assert resp.status_code == 201
    assert resp.json()["priority"] == "Urgent"


def test_order_invalid_priority_rejected_on_update(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300030")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    resp = client.put(f"/api/orders/{order['id']}", json={"priority": "Somewhat Important"})
    assert resp.status_code == 422


def test_order_list_filter_by_priority(client, test_user):
    _login(client, test_user)
    c1 = _create_client(client, phone="9812300031")
    c2 = _create_client(client, phone="9812300032")
    client.post("/api/orders/", json={
        "client_id": c1["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "priority": "Urgent",
    })
    client.post("/api/orders/", json={
        "client_id": c2["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "priority": "Low",
    })
    resp = client.get("/api/orders/", params={"priority": "Urgent"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert all(o["priority"] == "Urgent" for o in results)


def test_cancelled_order_cannot_be_reopened(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300024")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})
    assert resp.status_code == 200
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Material Purchase"})
    assert resp.status_code == 400
    # Re-fetch to confirm the status genuinely did not change server-side,
    # not just that the response was rejected.
    resp = client.get(f"/api/orders/{order['id']}")
    assert resp.json()["project_status"] == "Cancelled"


def test_cancelled_order_status_set_to_cancelled_again_is_a_noop(client, test_user):
    _login(client, test_user)
    c = _create_client(client, phone="9812300025")
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000",
    }).json()
    client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})
    resp = client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})
    assert resp.status_code == 200


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
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
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

    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
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
    """Scans every chat_* domain module (chat_service.py's dispatch
    core plus the 5 domain modules it delegates to - split out of what
    was previously all one file) since the regression this guards
    against - the chatbot directly constructing/mutating an Estimate
    or Order row rather than going through the propose-confirm flow -
    could equally be introduced in any of them, not just the dispatch
    core."""
    import app.modules.ai.orchestration as chat_service
    import app.modules.inventory.services as chat_inventory
    import app.modules.sales.services as chat_sales
    import app.modules.hr.services as chat_hr
    import app.modules.operations.services as chat_operations
    import app.modules.catalog.services as chat_catalog
    import app.modules.ai.agents as agent_service
    import inspect

    for module in (chat_service, chat_inventory, chat_sales, chat_hr, chat_operations, chat_catalog, agent_service):
        source = inspect.getsource(module)
        assert not re.search(r"\bEstimate\s*\(", source), f"{module.__name__} must never construct Estimate(...) directly"
        assert not re.search(r"\bOrder\s*\(", source), f"{module.__name__} must never construct Order(...) directly"
        for bad in ("create_estimate", "update_estimate", "delete_estimate", "accept_estimate",
                    "approve_estimate", "reject_estimate", "convert_estimate",
                    "create_order", "update_order", "delete_order", "cancel_order"):
            assert bad not in source, f"{module.__name__} must not contain {bad!r}"


def test_chat_service_never_proposes_estimate_or_order_write_action():
    import app.modules.ai.orchestration as chat_service
    import app.modules.inventory.services as chat_inventory
    import app.modules.sales.services as chat_sales
    import app.modules.hr.services as chat_hr
    import app.modules.operations.services as chat_operations
    import app.modules.catalog.services as chat_catalog
    import inspect

    forbidden = {
        "create_estimate", "update_estimate", "delete_estimate", "accept_estimate", "approve_estimate",
        "reject_estimate", "convert_estimate", "create_order", "update_order", "delete_order", "cancel_order",
    }
    for module in (chat_service, chat_inventory, chat_sales, chat_hr, chat_operations, chat_catalog):
        source = inspect.getsource(module)
        action_types = re.findall(r'action_type\s*=\s*"([^"]+)"', source)
        assert not (set(action_types) & forbidden), f"{module.__name__} proposes a forbidden estimate/order action"


# ---------------------------------------------------------------------
# Chatbot: order products query
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
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
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
    from app.modules.sales.models import Estimate, Order

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
# Client Master regression - must still work
# ---------------------------------------------------------------------

# ===========================================================================
# Order creation basics (from test_orders.py)
# ===========================================================================

def _create_client_id(client):
    resp = client.post("/api/clients/", json={
        "client_code": "CL-TEST", "name": "Test Client", "phone": "9999999999",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_order(client, client_id):
    resp = client.post("/api/orders/", json={
        "order_code": "WC-TEST-001", "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "100000.00", "advance": "20000.00",
    })
    assert resp.status_code == 201
    return resp.json()


def test_order_starts_with_advance_as_received(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)
    assert float(order["total_received"]) == 20000.0
    assert float(order["balance"]) == 80000.0


def test_payment_updates_order_totals(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "receipt_code": "RCPT-TEST-001", "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "30000.00",
    })
    assert resp.status_code == 201

    updated_order = client.get(f"/api/orders/{order['id']}").json()
    assert float(updated_order["total_received"]) == 50000.0
    assert float(updated_order["balance"]) == 50000.0


def test_order_profitability_reflects_expenses(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)

    client.post("/api/project-expenses/", json={
        "expense_code": "EXP-TEST-001", "date": "2026-08-02T00:00:00", "order_id": order["id"],
        "category": "Raw Material", "amount": "40000.00",
    })

    profitability = client.get(f"/api/orders/{order['id']}/profitability").json()
    assert profitability["project_expenses"] == 40000.0
    assert profitability["estimated_gross_profit"] == 60000.0


def test_client_endpoint_requires_auth(client):
    resp = client.get("/api/clients/")
    assert resp.status_code == 401


def test_payments_filtered_by_client_across_multiple_orders(client, test_user):
    _login(client, test_user)
    client_resp = client.post("/api/clients/", json={"name": "Multi-Order Client", "phone": "9000010155"})
    client_id = client_resp.json()["id"]

    order1 = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Wardrobe",
        "order_date": "2026-08-01T00:00:00", "order_value": "40000.00", "advance": "0",
    }).json()
    order2 = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Bed",
        "order_date": "2026-08-02T00:00:00", "order_value": "60000.00", "advance": "0",
    }).json()

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order1["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "10000.00",
    })
    client.post("/api/payments/", json={
        "date": "2026-08-06T00:00:00", "order_id": order2["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "15000.00",
    })

    # A single client_id call should return both payments, across both orders,
    # without the caller needing to fetch per-order.
    resp = client.get("/api/payments/", params={"client_id": client_id})
    assert resp.status_code == 200
    amounts = sorted(float(p["amount"]) for p in resp.json())
    assert amounts == [10000.0, 15000.0]


def test_payments_client_filter_excludes_other_clients(client, test_user):
    _login(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "Client A", "phone": "9000010156"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "Client B", "phone": "9000010157"}).json()["id"]

    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-01T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_a["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "5000.00",
    })
    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_b["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "7000.00",
    })

    resp = client.get("/api/payments/", params={"client_id": client_a})
    payments = resp.json()
    assert len(payments) == 1
    assert float(payments[0]["amount"]) == 5000.0


def test_advance_is_not_lost_when_a_payment_is_recorded_afterward(client, test_user):
    """Regression test for a real bug found during integration testing:
    recompute_totals() summed only Payment rows, but the advance amount
    is stored directly on the Order at creation (never as its own
    Payment record) - so total_received would silently drop to just the
    newest payment the instant any payment was recorded afterward,
    making the original advance vanish from the running total."""
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    client_id = client.post("/api/clients/", json={"name": "Advance Regression Client", "phone": "9000010158"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00",
        "order_value": "100000.00", "advance": "30000.00",
    }).json()
    assert order["total_received"] == "30000.00"

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "20000.00",
    })

    order_after = client.get(f"/api/orders/{order['id']}").json()
    # The advance (30000) must still be reflected, not just the new payment (20000).
    assert order_after["total_received"] == "50000.00"
    assert order_after["balance"] == "50000.00"

# ===========================================================================
# Order line item validation (from test_order_items.py)
# ===========================================================================

def _product(client, name):
    return client.post("/api/products/", json={"name": name, "unit": "Nos"}).json()["id"]


def test_order_with_items_computes_order_value_from_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Items Test Client", "phone": "9000010137"}).json()["id"]
    wardrobe_id = _product(client, "Wardrobe")
    installation_id = _product(client, "Installation")

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "10000.00",
        "items": [
            {"description": "Wardrobe", "category": "Furniture", "quantity": "1", "unit": "Nos", "rate": "85000.00", "product_id": wardrobe_id},
            {"description": "Installation", "category": "Installation", "quantity": "1", "unit": "Lot", "rate": "10000.00", "product_id": installation_id},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["amount"] == "85000.00"
    assert body["order_value"] == "95000.00"
    assert body["balance"] == "85000.00"  # 95000 - 10000 advance
    assert body["items_subtotal"] == "95000.00"


def test_item_amount_is_server_computed(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Item Trust Client", "phone": "9000010138"}).json()["id"]
    product_id = _product(client, "Test Item")

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Test Item", "quantity": "4", "rate": "500.00", "amount": "999999.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    assert resp.json()["items"][0]["amount"] == "2000.00"


def test_order_created_from_estimate_copies_items_and_links_back(client, test_user):
    """Priority 1B's exact workflow: Estimate -> Estimate Items -> Order
    -> Order Items, with the estimate linked back to the order it produced."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate To Order Client", "phone": "9000010139"}).json()["id"]
    kitchen_id = _product(client, "Modular Kitchen")
    hardware_id = _product(client, "Hardware")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [
            {"description": "Modular Kitchen", "category": "Furniture", "quantity": "1", "unit": "Lot", "rate": "250000.00", "product_id": kitchen_id},
            {"description": "Hardware", "category": "Hardware", "quantity": "1", "unit": "Lot", "rate": "30000.00", "product_id": hardware_id},
        ],
    }).json()
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "sent"})
    client.put(f"/api/estimates/{estimate['id']}", json={"status": "approved"})

    order_resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "50000.00",
        "from_estimate_id": estimate["id"],
    })
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert len(order["items"]) == 2
    assert order["order_value"] == "280000.00"
    descriptions = {item["description"] for item in order["items"]}
    assert descriptions == {"Modular Kitchen", "Hardware"}
    # Each copied item traces back to the estimate line it came from,
    # AND preserves the exact same Product ID (Product ID requirement).
    assert all(item["source_estimate_item_id"] is not None for item in order["items"])
    product_ids = {item["product_id"] for item in order["items"]}
    assert product_ids == {kitchen_id, hardware_id}

    # The estimate itself is now linked to the order it produced.
    estimate_after = client.get(f"/api/estimates/{estimate['id']}").json()
    assert estimate_after["order_id"] == order["id"]


def test_order_without_items_still_works_with_flat_order_value(client, test_user):
    """Backward compatibility - an order can still be created the old
    way, with just a flat order_value and no items."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Flat Order Value Client", "phone": "9000010140"}).json()["id"]

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00",
        "order_value": "50000.00", "advance": "10000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["items"] == []
    assert body["items_subtotal"] is None
    assert body["order_value"] == "50000.00"


def test_updating_order_items_replaces_full_set_and_recomputes_value(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Update Order Items Client", "phone": "9000010141"}).json()["id"]
    original_id = _product(client, "Original Item")
    new_id = _product(client, "New Item")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Original Item", "quantity": "1", "rate": "10000.00", "product_id": original_id}],
    }).json()

    resp = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "New Item", "quantity": "2", "rate": "7000.00", "product_id": new_id}],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "New Item"
    assert body["order_value"] == "14000.00"
    assert body["balance"] == "14000.00"


def test_order_still_gets_business_id_with_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Business ID Items Client", "phone": "9000010142"}).json()["id"]
    product_id = _product(client, "Item")
    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Item", "quantity": "1", "rate": "1000.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10


def test_payment_status_reflects_actual_payment_state(client, test_user):
    """Priority 3's explicit requirement - Payment Status derived from
    the same authoritative balance/total_received fields, not a
    separately-maintained column that could drift out of sync."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Status Client", "phone": "9000010143"}).json()["id"]

    unpaid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()
    assert unpaid["payment_status"] == "Unpaid"

    partially_paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "20000.00",
    }).json()
    assert partially_paid["payment_status"] == "Partially Paid"

    paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "50000.00",
    }).json()
    assert paid["payment_status"] == "Paid"

    # Recording an additional payment against the partially-paid order
    # must move it to Paid - proving payment_status stays in sync via
    # the same recompute_totals() path, not a stale snapshot.
    client.post("/api/payments/", json={
        "date": "2026-08-14T00:00:00", "order_id": partially_paid["id"],
        "payment_type": "Progress Payment", "payment_mode": "Bank", "amount": "30000.00",
    })
    updated = client.get(f"/api/orders/{partially_paid['id']}").json()
    assert updated["payment_status"] == "Paid"

# ===========================================================================
# Estimate line item computation (from test_estimate_line_items.py; reuses
# the _product helper from the order-items section above, confirmed identical)
# ===========================================================================
def test_estimate_with_multiple_line_items_computes_correct_totals(client, test_user):
    """The brief's own example figures - Wardrobe(2x85000) + Hardware(1x20000)
    + Installation(1x10000) = 200000 subtotal, with a 5000 discount and 18% GST."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Line Item Test Client", "phone": "9000010066"}).json()["id"]
    wardrobe_id = _product(client, "Wardrobe")
    hardware_id = _product(client, "Hardware")
    installation_id = _product(client, "Installation")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "discount": "5000.00", "tax_percent": "18",
        "line_items": [
            {"description": "Wardrobe", "category": "Furniture", "quantity": "2", "unit": "Nos", "rate": "85000.00", "product_id": wardrobe_id},
            {"description": "Hardware", "category": "Hardware", "quantity": "1", "unit": "Lot", "rate": "20000.00", "product_id": hardware_id},
            {"description": "Installation", "category": "Installation", "quantity": "1", "unit": "Lot", "rate": "10000.00", "product_id": installation_id},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["line_items"]) == 3
    assert body["line_items"][0]["amount"] == "170000.00"  # 2 * 85000, server-computed
    assert body["subtotal"] == "200000.00"
    assert body["tax_amount"] == "35100.00"  # (200000-5000) * 18% = 35100
    assert body["total_cost"] == "230100.00"  # 195000 + 35100


def test_line_item_amount_is_server_computed_not_trusted_from_client(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Trust Server Client", "phone": "9000010067"}).json()["id"]
    product_id = _product(client, "Test Item")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Test Item", "quantity": "3", "rate": "1000.00", "amount": "999999.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    # amount isn't even accepted on the input schema - server always computes qty*rate.
    assert resp.json()["line_items"][0]["amount"] == "3000.00"


def test_invalid_category_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Bad Category Client", "phone": "9000010068"}).json()["id"]
    product_id = _product(client, "Mystery Item")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Mystery Item", "category": "NotARealCategory", "quantity": "1", "rate": "500.00", "product_id": product_id}],
    })
    assert resp.status_code == 422


def test_estimate_with_no_line_items_falls_back_to_legacy_fields(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Legacy Fields Client", "phone": "9000010069"}).json()["id"]

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "100000.00", "labor_cost": "40000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["line_items"] == []
    assert body["subtotal"] == "140000.00"
    assert body["total_cost"] == "165200.00"


def test_updating_line_items_replaces_the_full_set_and_recomputes(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Update Line Items Client", "phone": "9000010070"}).json()["id"]
    original_id = _product(client, "Original Item")
    replacement_a_id = _product(client, "Replacement Item A")
    replacement_b_id = _product(client, "Replacement Item B")
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Original Item", "quantity": "1", "rate": "10000.00", "product_id": original_id}],
    }).json()
    assert estimate["subtotal"] == "10000.00"

    resp = client.put(f"/api/estimates/{estimate['id']}", json={
        "line_items": [
            {"description": "Replacement Item A", "quantity": "2", "rate": "5000.00", "product_id": replacement_a_id},
            {"description": "Replacement Item B", "quantity": "1", "rate": "3000.00", "product_id": replacement_b_id},
        ],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["line_items"]) == 2
    assert body["subtotal"] == "13000.00"  # 10000 + 3000, not 10000+10000+3000
    assert not any(item["description"] == "Original Item" for item in body["line_items"])


def test_revision_copies_line_items_to_the_new_version(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Revision Line Items Client", "phone": "9000010071"}).json()["id"]
    product_id = _product(client, "Kitchen Unit")
    original = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Kitchen Unit", "quantity": "1", "rate": "150000.00", "product_id": product_id}],
    }).json()

    resp = client.post(f"/api/estimates/{original['id']}/revise")
    assert resp.status_code == 201
    revision = resp.json()
    assert revision["version"] == 2
    assert len(revision["line_items"]) == 1
    assert revision["line_items"][0]["description"] == "Kitchen Unit"
    assert revision["line_items"][0]["product_id"] == product_id  # Product ID preserved across revision
    assert revision["subtotal"] == "150000.00"


def test_estimate_still_gets_business_id_with_line_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Business ID Line Items Client", "phone": "9000010072"}).json()["id"]
    product_id = _product(client, "Item")
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Item", "quantity": "1", "rate": "1000.00", "product_id": product_id}],
    })
    assert resp.status_code == 201
    assert resp.json()["business_id"] is not None
    assert len(resp.json()["business_id"]) == 10


# ---------------------------------------------------------------------
# Product ID requirement (new): mandatory, validated, authoritative
# ---------------------------------------------------------------------

def test_line_item_without_product_id_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Product ID Client", "phone": "9000010073"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Freeform Item", "quantity": "1", "rate": "1000.00"}],
    })
    assert resp.status_code == 422
    assert "Product ID is required" in str(resp.json())


def test_line_item_with_invalid_product_id_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Invalid Product ID Client", "phone": "9000010074"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Fake Item", "quantity": "1", "rate": "1000.00", "product_id": 999999}],
    })
    assert resp.status_code == 400
    assert "Invalid Product ID" in str(resp.json())


def test_line_item_response_includes_product_name_from_master(client, test_user):
    """Product Name displayed must come from Product Master, not the
    freeform description the user typed."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Product Name Display Client", "phone": "9000010075"}).json()["id"]
    product = client.post("/api/products/", json={"name": "6 Seater Dining Table", "unit": "Nos"}).json()

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Dining table - client's own wording", "quantity": "1", "rate": "25000", "product_id": product["id"]}],
    })
    assert resp.status_code == 201
    assert resp.json()["line_items"][0]["product_name"] == "6 Seater Dining Table"


def test_inactive_product_cannot_be_used_in_new_estimate(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Inactive Product Client", "phone": "9000010076"}).json()["id"]
    product = client.post("/api/products/", json={"name": "Discontinued Item", "unit": "Nos"}).json()
    client.put(f"/api/products/{product['id']}", json={"is_active": False})

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Discontinued Item", "quantity": "1", "rate": "1000", "product_id": product["id"]}],
    })
    assert resp.status_code == 400

# ===========================================================================
# Order profitability material cost (from test_order_profitability_material_cost.py)
# ===========================================================================

"""Tests for an explicit requirement - actual profitability
must not be represented as just Order Value - Project Expenses when
real material issue cost data exists. Labour cost is deliberately
excluded (no genuine time-tracking-to-wage data exists), not
fabricated."""


def test_profitability_includes_real_material_issue_cost(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Material Cost Client", "phone": "9000010149"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Profitability Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "2000.00",
    }).json()

    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "10", "unit": "Sheets",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    assert resp.status_code == 200
    body = resp.json()
    assert body["material_cost"] == 20000.0  # 10 sheets * 2000/sheet
    assert body["actual_direct_costs"] == 20000.0  # no project expenses in this test
    assert body["estimated_gross_profit"] == 80000.0  # 100000 - 20000


def test_profitability_combines_material_cost_and_project_expenses(client, test_user):
    """The core fix - previously this order's gross profit would have
    only subtracted the 15000 expense, silently ignoring the 20000 of
    real material cost."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Combined Cost Client", "phone": "9000010150"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Combined Cost Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "2000.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "10", "unit": "Sheets",
    })
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-15T00:00:00", "expense_type": "Transport", "amount": "15000.00",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["project_expenses"] == 15000.0
    assert body["material_cost"] == 20000.0
    assert body["actual_direct_costs"] == 35000.0
    assert body["estimated_gross_profit"] == 65000.0  # 100000 - 35000, not just 100000 - 15000


def test_labour_cost_attributed_from_completed_task_days(client, test_user):
    """Family P0.45: Employee.monthly_salary / 26 per distinct
    (employee, date) among this order's DONE tasks - not per task."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Labour Cost Client A", "phone": "9000010160"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Labour Cost Employee A", "monthly_salary": "26000"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-15T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Cutting", "status": "DONE",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["labour_is_attributed"] is True
    assert body["labour_days"] == 1
    assert body["labour_cost"] == 1000.0  # 26000 / 26
    # The existing, pre-P0.45 keys must remain completely unaffected.
    assert body["actual_direct_costs"] == 0.0
    assert body["estimated_gross_profit"] == 100000.0
    # The new, labour-inclusive keys reflect it.
    assert body["total_direct_cost_with_labour"] == 1000.0
    assert body["gross_profit_with_labour"] == 99000.0


def test_labour_cost_does_not_double_count_same_day_multiple_tasks(client, test_user):
    """Two DONE tasks, same employee, same day, same order -> one
    labour-day, not two - the exact double-counting risk this
    attribution method must avoid."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Labour Cost Client B", "phone": "9000010161"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Labour Cost Employee B", "monthly_salary": "26000"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-15T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Cutting", "status": "DONE",
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-15T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Assembly", "status": "DONE",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["labour_days"] == 1
    assert body["labour_cost"] == 1000.0


def test_labour_cost_counts_different_days_separately(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Labour Cost Client C", "phone": "9000010162"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Labour Cost Employee C", "monthly_salary": "26000"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-15T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Day 1", "status": "DONE",
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-16T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Day 2", "status": "DONE",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["labour_days"] == 2
    assert body["labour_cost"] == 2000.0


def test_labour_cost_ignores_incomplete_tasks(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Labour Cost Client D", "phone": "9000010163"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Labour Cost Employee D", "monthly_salary": "26000"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-15T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Still working", "status": "DOING",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["labour_is_attributed"] is False
    assert body["labour_days"] == 0
    assert body["labour_cost"] == 0.0


def test_labour_cost_unattributed_when_no_task_work_at_all(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Labour Cost Client E", "phone": "9000010164"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["labour_is_attributed"] is False
    assert body["labour_days"] == 0
    assert "No completed" in body["labour_method"]


def test_order_with_no_material_issued_has_zero_material_cost(client, test_user):
    """An order with only expenses and no material issued must not
    show a fabricated material cost - genuinely zero, honestly."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Material Client", "phone": "9000010151"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-15T00:00:00", "expense_type": "Labour", "amount": "5000.00",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["material_cost"] == 0.0
    assert body["estimated_gross_profit"] == 45000.0


def test_material_issued_to_a_different_order_does_not_affect_this_order(client, test_user):
    """Material cost must be correctly scoped per order, not leak
    across orders that happen to use the same material."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Isolation Cost Client", "phone": "9000010152"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Shared Cost Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "1000.00",
    }).json()

    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order_a["id"], "material_id": material["id"],
        "quantity_issued": "5", "unit": "Sheets",
    })

    order_a_profit = client.get(f"/api/orders/{order_a['id']}/profitability").json()
    order_b_profit = client.get(f"/api/orders/{order_b['id']}/profitability").json()
    assert order_a_profit["material_cost"] == 5000.0
    assert order_b_profit["material_cost"] == 0.0


def test_material_cost_supports_decimal_quantities(client, test_user):
    """Consistent with the decimal-quantity fix - material cost must
    correctly reflect a fractional quantity issued (e.g. 2.5 kg)."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Decimal Cost Client", "phone": "9000010153"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Decimal Cost Adhesive", "unit": "Kg", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "2.5", "unit": "Kg",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability").json()
    assert resp["material_cost"] == 1000.0  # 2.5 kg * 400/kg


def test_dashboard_excel_and_chatbot_all_reflect_the_same_material_cost(client, test_user):
    """Single source of truth check across all three consumers named in
    the brief - dashboard, Excel export, and chatbot must not disagree."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Consistency Check Client", "phone": "9000010154"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Consistency Check Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "4", "unit": "Sheets",
    })

    dashboard_row = next(
        r for r in client.get("/api/dashboard/orders").json()["order_profitability"]
        if r["order_id"] == order["order_code"]
    )
    order_detail = client.get(f"/api/orders/{order['id']}/profitability").json()

    assert dashboard_row["material_cost"] == order_detail["material_cost"] == 2000.0

# ===========================================================================
# Order balance recomputation (from test_order_payment_recomputation.py)
# ===========================================================================

"""Explicit regression suite for order balance recomputation: advance +
payment + edited payment + multiple payments must all correctly
recompute Order.total_received/balance, and the stored advance must
never disappear during recomputation - a real bug documented in
Order.recompute_totals()'s own docstring.

"Deleted payment" is NOT covered here - checked directly and
confirmed no delete endpoint exists for payments at all (a
deliberate design choice: payments are a record of money that
actually changed hands, and deletability would risk hiding real
transactions or silently breaking balance consistency). There is
nothing to regression-test for a feature that does not exist."""


def test_advance_alone_is_reflected_in_total_received(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Advance Only Test Client", "phone": "9000010144"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    assert float(order["total_received"]) == 10000.0
    assert float(order["balance"]) == 40000.0


def test_advance_does_not_disappear_after_a_payment_is_recorded(client, test_user):
    """The exact bug documented in recompute_totals()'s own docstring -
    the advance must still be counted after a payment is added, not
    silently dropped."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Advance Persistence Test Client", "phone": "9000010145"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    })

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 25000.0  # 10000 advance + 15000 payment, advance still present
    assert float(refreshed["balance"]) == 25000.0


def test_multiple_payments_accumulate_correctly_with_advance(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Multiple Payments Test Client", "phone": "9000010146"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    })
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "Cash", "amount": "10000",
    })

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 35000.0  # 10000 + 15000 + 10000
    assert float(refreshed["balance"]) == 15000.0


def test_editing_a_payment_amount_recomputes_correctly(client, test_user):
    """The exact scenario named explicitly - an edited
    payment must correctly recompute the order's totals, not just a
    newly-created one."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Edited Payment Test Client", "phone": "9000010147"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "Cash", "amount": "10000",
    })

    client.put(f"/api/payments/{payment['id']}", json={"amount": "20000"})

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 40000.0  # 10000 advance + 20000 edited + 10000 second payment
    assert float(refreshed["balance"]) == 10000.0


def test_no_delete_endpoint_exists_for_payments(client, test_user):
    """Documents the deliberate design choice this suite's scope
    depends on, rather than silently assume it - if a delete
    endpoint is ever added, this test will fail and signal that the
    "deleted payment" regression scenario now needs real coverage."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Delete Test Client", "phone": "9000010148"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Advance",
        "payment_mode": "Cash", "amount": "5000",
    }).json()

    resp = client.delete(f"/api/payments/{payment['id']}")
    assert resp.status_code in (404, 405)


# ===========================================================================
# Order/estimate PDF exports and invoice history (from test_client_hr_and_export_features.py)
# ===========================================================================
def test_order_estimate_pdf_downloads(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)

    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_payments_export_requires_master_or_manager(client, test_user):
    _login(client, test_user)  # test_user fixture is role=master, so this succeeds
    resp = client.get("/api/reports/payments.xlsx")
    assert resp.status_code == 200


def test_order_invoice_pdf_downloads(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)

    resp = client.get(f"/api/reports/orders/{order['id']}/invoice.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_invoice_reflects_payment_history(client, test_user):
    _login(client, test_user)
    client_id = _create_client_id(client)
    order = _create_order(client, client_id)

    client.post("/api/payments/", json={
        "receipt_code": "RCPT-INV-001", "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "15000.00",
    })

    resp = client.get(f"/api/reports/orders/{order['id']}/invoice.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


# ===========================================================================
# Order balance recomputation (from test_client_hr_and_export_features.py)
# ===========================================================================
def test_order_balance_recomputes_correctly_when_items_change(client, test_user):
    """Confirms the consolidated recompute_totals() call still produces
    the correct balance after an item-driven order_value change,
    verifying the refactor didn't change behavior."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Recompute Totals Test Client", "phone": "9000010176"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Custom wardrobe", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "2000",
    }).json()
    assert float(order["balance"]) == 8000.0

    updated = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "Custom wardrobe", "quantity": "1", "rate": "25000", "amount": "25000", "product_id": product_id}],
    }).json()
    assert float(updated["order_value"]) == 25000.0
    assert float(updated["balance"]) == 23000.0  # 25000 - 2000 advance, matching recompute_totals()'s formula


def test_order_balance_stays_consistent_after_a_payment(client, test_user):
    """The same balance field, now updated via a completely different
    code path (payments.py) - both must agree on the same number."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Consistency Test Client", "phone": "9000010177"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "20000", "advance": "0",
    }).json()
    client.post("/api/payments/", json={"order_id": order["id"], "amount": "5000", "payment_date": "2026-08-19T00:00:00"})

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["balance"]) == 15000.0



# ===========================================================================
# Estimate export rate limiting (from test_client_hr_and_export_features.py)
# ===========================================================================
def test_estimates_export_is_rate_limited(client, test_user):
    _login(client, test_user)
    from app.platform.configuration.config import settings
    responses = [client.get("/api/reports/estimates.xlsx") for _ in range(settings.RATE_LIMIT_EXPORT_PER_MINUTE + 3)]
    assert any(r.status_code == 429 for r in responses)

# ===========================================================================
# Estimate versioning (from test_admin_and_ai_gateway.py, itself from
# test_estimate_versioning.py) - the client-creation helper here reuses
# this file's existing _create_client rather than the incoming
# duplicate (different signature - returned a bare id, not a dict).
# ===========================================================================
# From test_estimate_versioning.py
# ===========================================================================
def test_revise_creates_new_version_not_overwrite(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client, name="Versioning Test Client", phone="9000010075")["id"]

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
    client_id = _create_client(client, name="Versioning Test Client 2", phone="9000010078")["id"]

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

# ===========================================================================

# ===========================================================================
# Estimate tax/total computation (from test_admin_and_ai_gateway.py's
# former test_estimates_hr.py section)
# ===========================================================================
def test_estimate_computes_tax_and_total(client, test_user):
    _login(client, test_user)
    create_resp = client.post("/api/clients/", json={"name": "Estimate Client", "phone": "9000010076"})
    client_id = create_resp.json()["id"]

    resp = client.post("/api/estimates/", json={
        "client_id": client_id,
        "material_cost": "50000.00", "labor_cost": "20000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["tax_amount"]) == 12600.0
    assert float(body["total_cost"]) == 82600.0

# (Relocated a second time - was briefly in test_admin_and_ai_gateway.py,
# which was itself a grab-bag needing correction; this is the correct
# sales-domain home.)
# ===========================================================================
# Order-risk AI workspace (from test_ai_workspace_order_risk.py) - a real
# persisted artifact combining only genuinely existing data (linked tasks,
# production jobs, materials issued), never a fabricated materials-shortage
# figure. Includes the read-time re-redaction guarantee: a report created by
# master must not leak payment data to an employee viewing it later.
# ===========================================================================
def test_blocking_query_creates_persisted_report(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Client", "phone": "9000010001"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "60000", "advance": "10000",
    }).json()
    employee = client.post("/api/employees/", json={"name": "AI Workspace Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-20T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Fit hardware", "status": "BLOCKED", "delay_reason": "Waiting for hinges",
    })

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    assert "AT RISK" in resp.json()["response"]
    assert "hinges" in resp.json()["response"].lower()

    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert len(reports) == 1
    assert reports[0]["risk_level"] == "AT_RISK"
    assert reports[0]["findings"]["blocked_tasks"][0]["reason"] == "Waiting for hinges"


def test_chatbot_order_risk_correctly_reports_critical_not_on_track(client, test_user):
    """Regression test for a severe bug: the chatbot's risk_level-to-
    text mapping only matched the exact string 'AT_RISK', so the newer
    CRITICAL value fell through to the else branch and was reported to
    the Master as "ON TRACK" - the opposite of the truth."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chatbot Critical Client", "phone": "9000010003"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Chatbot Critical Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Overdue critical work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()["response"]
    assert "CRITICAL" in body
    assert "ON TRACK" not in body


def test_order_with_no_blockers_is_on_track(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace On Track Client", "phone": "9000010002"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "20000", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert "ON TRACK" in resp.json()["response"]

    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert reports[0]["risk_level"] == "ON_TRACK"


def test_order_blocking_query_includes_real_material_shortage(client, test_user):
    """Family 130 - "what's blocking this order" must include a real
    material shortage against this order's own BOM, reusing
    StockService.calculate_order_material_requirements - previously
    this workspace never computed a material figure at all, even
    though the order has a real, unmet BOM requirement."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Blocking Query Shortage Sheet", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "1",
    }).json()
    supplier = client.post("/api/suppliers/", json={"name": "Blocking Query Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "300.00", "lead_time_days": 3,
    })
    product = client.post("/api/products/", json={
        "name": "Blocking Query Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Blocking Query Client", "phone": "9000010700"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()["response"]
    assert "AT RISK" in body
    assert "Blocking Query Shortage Sheet" in body
    assert "Blocking Query Supplier" in body

    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert reports[0]["risk_level"] == "AT_RISK"
    shortages = reports[0]["findings"]["material_shortages"]
    assert len(shortages) == 1
    assert shortages[0]["material_name"] == "Blocking Query Shortage Sheet"
    assert shortages[0]["supplier_options"][0]["supplier_name"] == "Blocking Query Supplier"


def test_deictic_followup_triggers_order_risk_check(client, test_user):
    """"usme kya scene hai" style follow-up, using last turn's
    conversational memory mechanism together with this one."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Deictic Client", "phone": "9000010003"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "35000", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "tell me about this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    last_entity = first.json()["last_entity"]

    followup = client.post("/api/chat/", json={
        "message": "kya problem hai usme",
        "context": {"last_entity": last_entity},
    })
    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert len(reports) == 1


def test_employee_viewing_master_created_report_does_not_see_payment(client, test_user, db_session):
    """The core security guarantee - re-redaction happens at read
    time based on the CURRENT viewer's role, not the role that
    created the report."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Redaction Client", "phone": "9000010004"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "50000", "advance": "5000",
    }).json()

    # Master creates the report - findings include pending_payment.
    client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    master_view = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert "pending_payment" in master_view[0]["findings"]

    employee = client.post("/api/employees/", json={"name": "AI Workspace Redaction Employee"}).json()
    user = User(
        username="aiworkspaceredactionuser", email="aiworkspaceredactionuser@example.com",
        full_name="AI Workspace Redaction User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "aiworkspaceredactionuser@example.com", "password": "EmpPass1!"})

    employee_view = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert "pending_payment" not in employee_view[0]["findings"]


def test_replacing_order_items_leaves_a_traceable_audit_record(client, test_user, db_session):
    """P0.1 section 8 - item changes must not silently leave downstream
    information untraceable. Previously, replacing an order's items
    hard-deleted the old rows with no snapshot ever taken; the audit
    log recorded only a bare items_changed=True flag, permanently
    losing what the old items actually were."""
    from app.platform.audit.audit import AuditLog
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Item Trace Client", "phone": "9000010900"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Original Cabinet", "quantity": "1", "unit": "Piece", "rate": "10000"}],
    }).json()

    resp = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "Revised Cabinet", "quantity": "2", "unit": "Piece", "rate": "12000"}],
    })
    assert resp.status_code == 200

    log_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.module_name == "orders", AuditLog.record_id == order["id"], AuditLog.action == "update_order")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert log_entry is not None
    assert log_entry.old_value["items"][0]["description"] == "Original Cabinet"
    assert log_entry.old_value["items"][0]["rate"] == 10000.0
    assert log_entry.new_value["items"][0]["description"] == "Revised Cabinet"
    assert log_entry.new_value["items"][0]["quantity"] == 2.0


# ===========================================================================
# P0.50 - Delivery Risk Engine (extends compute_order_health, not a second
# engine). Dates are relative to actual current time since the underlying
# calculation uses datetime.utcnow(), not a fixed test clock.
# ===========================================================================

def _make_order_with_delivery(client, days_from_now, suffix, project_status=None):
    from datetime import datetime, timedelta
    c = client.post("/api/clients/", json={"name": f"Delivery Risk Client {suffix}", "phone": f"900001110{suffix}"}).json()
    delivery_date = (datetime.utcnow() + timedelta(days=days_from_now)).isoformat()
    payload = {
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": delivery_date,
    }
    order = client.post("/api/orders/", json=payload).json()
    if project_status:
        client.put(f"/api/orders/{order['id']}", json={"project_status": project_status})
    return order


def test_delivery_risk_watch_level_for_approaching_delivery_with_open_work(client, test_user):
    """P0.50 section 6 - a delivery 5 days out with open work is a
    genuine early warning (WATCH), distinct from the more urgent
    AT_RISK 3-day window - not the same 2-level bucket as before."""
    _login(client, test_user)
    order = _make_order_with_delivery(client, 5, "1")
    employee = client.post("/api/employees/", json={"name": "Delivery Risk Watch Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Prep materials", "status": "TO DO",
    })

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "WATCH"
    assert body["delivery_timing"]["days_remaining"] == 5
    assert body["delivery_timing"]["is_overdue"] is False


def test_delivery_risk_critical_when_overdue_and_still_open(client, test_user):
    """P0.50 - a delivery commitment already missed, with the order
    still not completed, is more severe than the generic AT_RISK the
    old 2-level model would have used for every non-trivial finding."""
    _login(client, test_user)
    order = _make_order_with_delivery(client, -2, "2")
    employee = client.post("/api/employees/", json={"name": "Delivery Risk Critical Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Still pending", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "CRITICAL"
    assert body["delivery_timing"]["is_overdue"] is True
    assert body["delivery_timing"]["urgency_text"] == "2 days overdue"
    assert body["next_action"]["type"] == "delivery_overdue"
    assert "already been missed" in body["business_impact"]


def test_delivery_risk_not_critical_when_overdue_but_completed(client, test_user):
    """An overdue delivery date on an order already marked Completed is
    not a live risk - the commitment was met (or the order closed) by
    the time work finished, whatever the original target date was."""
    _login(client, test_user)
    order = _make_order_with_delivery(client, -5, "3", project_status="Completed")

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] != "CRITICAL"
    assert body["readiness"]["delivery"] == "delivered"


def test_delivery_timing_reports_missing_date_honestly(client, test_user):
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "No Delivery Date Client", "phone": "9000011200"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    timing = resp.json()["delivery_timing"]
    assert timing["has_delivery_date"] is False
    assert timing["urgency_text"] == "Delivery date not set"


def test_health_evidence_carries_raw_shortage_numbers(client, test_user):
    """P0.50 section 9 - evidence must carry the actual numbers behind
    a reason, not just its sentence."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Health Evidence Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Health Evidence Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    c = client.post("/api/clients/", json={"name": "Health Evidence Client", "phone": "9000011300"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    evidence = resp.json()["evidence"]
    shortage_evidence = next(e for e in evidence if e["type"] == "material_shortage")
    assert shortage_evidence["required"] == 5.0
    assert shortage_evidence["available"] == 2.0
    assert shortage_evidence["shortage"] == 3.0
    assert "cannot fully proceed" in resp.json()["business_impact"]


def test_orders_export_includes_delivery_risk_columns(client, test_user):
    """P0.50 section 37 - the export must show the same risk
    classification as the API/UI (bulk_attention_flags), never a
    separately-calculated Excel-only value."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Export Risk Client", "phone": "9000011400"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Export Risk Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Export risk work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    resp = client.get("/api/reports/orders.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    header_row, data_rows = None, []
    for row in ws.iter_rows(values_only=True):
        if row and "Order Code" in row:
            header_row = list(row)
            continue
        if header_row and row and row[header_row.index("Order Code")] == order["order_code"]:
            data_rows.append(row)
    assert "Delivery Risk" in header_row
    assert "Risk Reason" in header_row
    risk_col = header_row.index("Delivery Risk")
    assert data_rows[0][risk_col] == "CRITICAL"


def test_production_summary_reflects_completed_and_pending_jobs(client, test_user):
    """P0.50 section 14 - the exact structured breakdown the spec's own
    example asks for (N jobs, completed: X, pending: Y)."""
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Production Summary Client", "phone": "9000011500"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    job1 = client.post("/api/production-jobs/", json={
        "date": "2026-07-01T00:00:00", "operation": "Cutting", "order_id": order["id"],
    }).json()
    client.put(f"/api/production-jobs/{job1['id']}", json={"status": "Completed"})
    client.post("/api/production-jobs/", json={
        "date": "2026-07-01T00:00:00", "operation": "Assembly", "order_id": order["id"],
    })

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    summary = resp.json()["production_summary"]
    assert summary["has_production_jobs"] is True
    assert summary["total_jobs"] == 2
    assert summary["completed_jobs"] == 1
    assert summary["pending_jobs"] == 1


def test_production_summary_reports_no_jobs_honestly(client, test_user):
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "No Production Client", "phone": "9000011501"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.json()["production_summary"]["has_production_jobs"] is False


def test_procurement_chain_distinguishes_no_purchase_from_purchase_placed(client, test_user):
    """P0.50 section 13 - the full narrative chain: shortage -> purchase
    required -> purchase not received. Evidence must distinguish "no
    purchase placed yet" from "a purchase exists but is insufficient"."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Procurement Chain Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Procurement Chain Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    c = client.post("/api/clients/", json={"name": "Procurement Chain Client", "phone": "9000011502"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/health")
    assert resp.status_code == 200
    evidence = next(e for e in resp.json()["evidence"] if e["type"] == "material_shortage")
    assert evidence["procurement_status"] == "no_purchase_placed"
    assert "no purchase has been placed yet" in resp.json()["business_impact"]

    # Now place a purchase that doesn't fully cover the gap (3 short).
    supplier = client.post("/api/suppliers/", json={"name": "Procurement Chain Supplier"}).json()
    client.post("/api/purchases/", json={
        "date": "2026-07-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "1", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "receipt_status": "Ordered",
    })

    resp2 = client.get(f"/api/orders/{order['id']}/health")
    evidence2 = next(e for e in resp2.json()["evidence"] if e["type"] == "material_shortage")
    assert evidence2["procurement_status"] == "purchase_placed_insufficient"
    assert "pending purchase is received" in resp2.json()["business_impact"]


def test_procurement_chain_flags_when_shortage_blocks_production(client, test_user):
    """The chain must genuinely connect a shortage to a specific
    blocked job by material, not just co-occur with an unrelated one."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Blocking Chain Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Blocking Chain Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    c = client.post("/api/clients/", json={"name": "Blocking Chain Client", "phone": "9000011503"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-07-01T00:00:00", "operation": "Cutting", "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.put(f"/api/production-jobs/{job['id']}", json={"blocker_reason": "Waiting for sheets"})

    resp = client.get(f"/api/orders/{order['id']}/health")
    evidence = next(e for e in resp.json()["evidence"] if e["type"] == "material_shortage")
    assert evidence["blocks_production"] is True


def test_what_if_shows_risk_impact_of_hypothetical_delivery_date(client, test_user):
    """P0.50 section 11 - moving an order's delivery date closer with
    open work must show the risk-level impact, using the exact same
    calculation as the real health endpoint, without touching the
    order's actual committed date."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "What If Client", "phone": "9000011504"}).json()
    order = client.post("/api/orders/", json={
        "client_id": c["id"], "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
        "delivery_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "What If Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "What if open work", "status": "TO DO",
    })

    hypothetical = (datetime.utcnow() + timedelta(days=2)).isoformat()
    resp = client.get(f"/api/orders/{order['id']}/what-if", params={"new_delivery_date": hypothetical})
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"]["risk_level"] == "ON_TRACK"
    assert body["simulated"]["risk_level"] in ("AT_RISK", "WATCH")
    assert body["risk_level_changed"] is True

    # The order's real, committed delivery date must be untouched.
    real_order = client.get(f"/api/orders/{order['id']}").json()
    assert real_order["delivery_date"] is not None
    assert real_order["delivery_date"][:10] != hypothetical[:10]


def test_what_if_requires_auth(client):
    resp = client.get("/api/orders/1/what-if", params={"new_delivery_date": "2026-09-01T00:00:00"})
    assert resp.status_code == 401


def test_what_if_unknown_order_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/orders/999999/what-if", params={"new_delivery_date": "2026-09-01T00:00:00"})
    assert resp.status_code == 404
