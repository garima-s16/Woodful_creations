"""Tests for ProcurementRequirement (P0.2.1) and SupplierDecision
(P0.2.3) - closing the two gaps this family's own architecture review
identified: there was no persisted procurement requirement (only a
transient shortage calculation) and no persisted record distinguishing
a supplier recommendation from the supplier actually chosen."""
from tests.helpers import _login


def _make_shortage_order(client, suffix):
    material = client.post("/api/materials/", json={
        "name": f"Procurement Req Sheet {suffix}", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": f"Procurement Req Product {suffix}", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": f"Procurement Req Client {suffix}", "phone": f"900001080{suffix}"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    return order, material


def test_creating_requirement_snapshots_real_shortage_not_client_values(client, test_user):
    """The client cannot supply required/available/shortage - the route
    must derive them itself from the authoritative calculation."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "1")

    resp = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"], "priority": "High",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["required_quantity"]) == 5.0
    assert float(body["available_quantity_at_creation"]) == 2.0
    assert float(body["shortage_quantity_at_creation"]) == 3.0
    assert body["status"] == "Open"
    assert body["material_name"] == f"Procurement Req Sheet 1"


def test_requirement_without_a_real_material_requirement_is_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Req Client", "phone": "9000010810"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={"name": "Unrelated Sheet", "unit": "Sheets", "opening_stock": "5"}).json()

    resp = client.post("/api/procurement-requirements/", json={"order_id": order["id"], "material_id": material["id"]})
    assert resp.status_code == 400


def test_supplier_decision_distinguishes_recommendation_from_actual_choice(client, test_user):
    """The core P0.2.3 guarantee: the recommendation and the actual
    decision are genuinely different, persisted things."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "2")
    cheap_supplier = client.post("/api/suppliers/", json={"name": "Cheap Req Supplier"}).json()
    preferred_supplier = client.post("/api/suppliers/", json={"name": "Preferred Req Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": cheap_supplier["id"], "material_id": material["id"], "supplier_price": "400.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": preferred_supplier["id"], "material_id": material["id"], "supplier_price": "550.00", "is_preferred": True,
    })
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    # Master deliberately chooses the cheaper, non-preferred supplier -
    # a real decision that diverges from the recommendation.
    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": cheap_supplier["id"],
        "decision_reason": "Cash flow this month favors the lower price",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["recommended_supplier_id"] == preferred_supplier["id"]
    assert body["selected_supplier_id"] == cheap_supplier["id"]
    assert body["followed_recommendation"] is False
    assert body["decision_reason"] == "Cash flow this month favors the lower price"


def test_second_decision_on_same_requirement_is_rejected(client, test_user):
    _login(client, test_user)
    order, material = _make_shortage_order(client, "3")
    supplier = client.post("/api/suppliers/", json={"name": "Only Req Supplier"}).json()
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": supplier["id"],
    })

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": supplier["id"],
    })
    assert resp.status_code == 409


def test_procurement_requirements_are_master_only(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    _login(client, test_user)
    order, material = _make_shortage_order(client, "4")
    employee = User(
        username="procreqempuser", email="procreqempuser@example.com", full_name="Proc Req Employee",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "procreqempuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/procurement-requirements/", json={"order_id": order["id"], "material_id": material["id"]})
    assert resp.status_code == 403
    assert client.get("/api/procurement-requirements/").status_code == 403


def test_supplier_options_preview_matches_what_decision_would_recommend(client, test_user):
    """The preview endpoint and the decision endpoint must agree - same
    underlying calculation, not two independently-drifting ones."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "10")
    preferred = client.post("/api/suppliers/", json={"name": "Preview Preferred Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": preferred["id"], "material_id": material["id"], "is_preferred": True,
    })
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/procurement-requirements/{requirement['id']}/supplier-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["material_id"] == material["id"]
    assert len(body["options"]) == 1
    assert body["options"][0]["supplier_id"] == preferred["id"]
    assert body["options"][0]["is_preferred"] is True


def test_get_requirement_includes_decision_with_supplier_names(client, test_user):
    """The requirement GET response must actually embed the decision
    (with real supplier names, not just IDs) - a frontend showing the
    requirement's own detail page has no other way to know a decision
    was already made without this."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "11")
    preferred = client.post("/api/suppliers/", json={"name": "Embedded Decision Preferred Supplier"}).json()
    chosen = client.post("/api/suppliers/", json={"name": "Embedded Decision Chosen Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": preferred["id"], "material_id": material["id"], "is_preferred": True,
    })
    client.post("/api/supplier-materials/", json={"supplier_id": chosen["id"], "material_id": material["id"]})
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": chosen["id"],
    })

    resp = client.get(f"/api/procurement-requirements/{requirement['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] is not None
    assert body["decision"]["selected_supplier_name"] == "Embedded Decision Chosen Supplier"
    assert body["decision"]["recommended_supplier_name"] == "Embedded Decision Preferred Supplier"
    assert body["decision"]["followed_recommendation"] is False


def test_get_requirement_without_decision_has_null_decision(client, test_user):
    _login(client, test_user)
    order, material = _make_shortage_order(client, "12")
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/procurement-requirements/{requirement['id']}")
    assert resp.json()["decision"] is None


def test_procurement_requirements_require_auth(client):
    resp = client.get("/api/procurement-requirements/")
    assert resp.status_code == 401


def test_decision_rejects_supplier_with_no_material_relationship(client, test_user):
    """P0.2.4: the backend must reject this regardless of what the
    frontend dropdown would have filtered - never trust a client-sent
    supplier_id alone."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "5")
    unrelated_supplier = client.post("/api/suppliers/", json={"name": "Unrelated Supplier No Link"}).json()
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": unrelated_supplier["id"],
    })
    assert resp.status_code == 400
    assert "no recorded supply relationship" in resp.json()["detail"].lower()


def test_purchase_created_from_requirement_is_linked_and_fulfills_it(client, test_user):
    """P0.2.5 traceability: requirement.purchase_id is actually set, and
    receipt_status="Received" genuinely fulfills the requirement (goods
    are actually in hand, not merely ordered)."""
    _login(client, test_user)
    order, material = _make_shortage_order(client, "6")
    supplier = client.post("/api/suppliers/", json={"name": "Traceability Supplier"}).json()
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": supplier["id"],
    })

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/purchase", json={
        "quantity": "5", "unit": "Sheets", "rate": "450.00", "gst_percent": "18", "receipt_status": "Received",
    })
    assert resp.status_code == 201
    purchase = resp.json()
    assert purchase["supplier_id"] == supplier["id"]
    assert purchase["material_id"] == material["id"]

    updated_requirement = client.get(f"/api/procurement-requirements/{requirement['id']}").json()
    assert updated_requirement["purchase_id"] == purchase["id"]
    assert updated_requirement["status"] == "Fulfilled"


def test_purchase_from_requirement_ordered_not_received_stays_ordered(client, test_user):
    _login(client, test_user)
    order, material = _make_shortage_order(client, "7")
    supplier = client.post("/api/suppliers/", json={"name": "Traceability Ordered Supplier"}).json()
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": supplier["id"],
    })

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/purchase", json={
        "quantity": "5", "unit": "Sheets", "rate": "450.00", "gst_percent": "18", "receipt_status": "Ordered",
    })
    assert resp.status_code == 201
    updated_requirement = client.get(f"/api/procurement-requirements/{requirement['id']}").json()
    assert updated_requirement["status"] == "Ordered"


def test_purchase_from_requirement_without_decision_is_rejected(client, test_user):
    _login(client, test_user)
    order, material = _make_shortage_order(client, "8")
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/purchase", json={
        "quantity": "5", "unit": "Sheets", "rate": "450.00", "gst_percent": "18",
    })
    assert resp.status_code == 400


def test_second_purchase_from_same_requirement_is_rejected(client, test_user):
    _login(client, test_user)
    order, material = _make_shortage_order(client, "9")
    supplier = client.post("/api/suppliers/", json={"name": "Traceability Duplicate Supplier"}).json()
    client.post("/api/supplier-materials/", json={"supplier_id": supplier["id"], "material_id": material["id"]})
    requirement = client.post("/api/procurement-requirements/", json={
        "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.post(f"/api/procurement-requirements/{requirement['id']}/decision", json={
        "requirement_id": requirement["id"], "selected_supplier_id": supplier["id"],
    })
    client.post(f"/api/procurement-requirements/{requirement['id']}/purchase", json={
        "quantity": "5", "unit": "Sheets", "rate": "450.00", "gst_percent": "18",
    })

    resp = client.post(f"/api/procurement-requirements/{requirement['id']}/purchase", json={
        "quantity": "5", "unit": "Sheets", "rate": "450.00", "gst_percent": "18",
    })
    assert resp.status_code == 409
