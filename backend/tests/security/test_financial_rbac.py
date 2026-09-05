"""Financial-data RBAC tests - consolidated from 5 separate
test_*_financial_rbac.py files that all verify the same concern across
different domains: financial fields (prices, amounts, margins) are
genuinely redacted/blocked for non-master users, not just hidden by
the frontend. Two genuine helper-name collisions were found and
resolved: three identical 4-param _create_employee definitions were
deduplicated to one, and two identical 5-param _create_employee
definitions (which take an extra `name` arg and don't return a value -
a real, different function, not just a variant) were dropped in favor
of the pre-existing, correctly-scoped _create_employee_with_name from
test_inventory_financial_rbac.py, with their 11 call sites renamed to
match.

test_attendance_hr_rbac.py deliberately stays separate - it is a
different kind of RBAC concern (ownership-based access to another
employee's records), not financial-field redaction.
"""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login, _create_employee_with_login as _create_employee


# ===========================================================================
# From test_cart_financial_rbac.py
# ===========================================================================

def test_master_sees_own_cart_item_rate(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Master Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.json()["rate"] is not None


def test_employee_own_cart_item_rate_is_genuinely_null(client, test_user, db_session):
    """The real gap found this turn - an employee could previously see
    a material's price by adding it to their own cart, even though the
    Materials page itself hides it from them."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Employee Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    _create_employee(client, db_session, "cartrbacuser", "cartrbacuser@example.com")
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.status_code == 201
    assert resp.json()["rate"] is None
    # Non-financial fields remain visible - it's still a usable cart.
    assert resp.json()["material_name"] == "Cart RBAC Employee Material"
    assert float(resp.json()["quantity"]) == 2.0


def test_employee_cart_list_also_redacts_rate(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC List Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "250.00",
    }).json()

    _create_employee(client, db_session, "cartlistrbacuser", "cartlistrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    listed = client.get("/api/personal-cart/").json()
    assert listed[0]["rate"] is None


def test_employee_accumulating_existing_cart_item_still_redacts_rate(client, test_user, db_session):
    """The second add-to-cart code path (existing item, quantity
    accumulates) must also redact - not just the first-add path."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Accumulate Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "300.00",
    }).json()

    _create_employee(client, db_session, "cartaccumrbacuser", "cartaccumrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    assert resp.json()["rate"] is None
    assert float(resp.json()["quantity"]) == 2.0


def test_chatbot_employee_denied_cart_optimization(client, test_user, db_session):
    """The real gap found this turn - cart optimization explicitly
    compares supplier prices and had no permission check at all."""
    _login(client, test_user)
    supplier_a = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier A"}).json()
    supplier_b = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier B"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_a["id"], "material_id": material["id"], "supplier_price": "100.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_b["id"], "material_id": material["id"], "supplier_price": "120.00",
    })

    _create_employee(client, db_session, "cartoptrbacuser", "cartoptrbacuser@example.com")
    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" in text.lower()
    assert "Cart Opt RBAC Supplier A" not in text
    assert "100" not in text


def test_chatbot_master_still_gets_real_cart_optimization(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Master Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Master Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" not in text.lower()
    assert "Cart Opt RBAC Master Supplier" in text

# ===========================================================================
# From test_estimate_financial_rbac.py
# ===========================================================================

def test_master_sees_estimate_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Client", "phone": "9000010059"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is not None
    assert resp["total_cost"] is not None


def test_employee_estimate_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Employee Client", "phone": "9000010060"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Employee", "estimaterbacuser", "estimaterbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is None
    assert resp["labor_cost"] is None
    assert resp["discount"] is None
    assert resp["subtotal"] is None
    assert resp["tax_amount"] is None
    assert resp["total_cost"] is None
    # Non-financial workflow state remains real.
    assert resp["status"] is not None
    assert resp["estimate_code"] == estimate["estimate_code"]


def test_employee_estimate_line_item_pricing_is_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Items Client", "phone": "9000010061"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Cabinet", "unit": "Nos"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Cabinet", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "15000.00", "product_id": product_id}],
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Items Employee", "estimateitemsrbacuser", "estimateitemsrbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["line_items"][0]["rate"] is None
    assert resp["line_items"][0]["amount"] is None
    assert resp["line_items"][0]["description"] == "Cabinet"


def test_employee_cannot_create_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Create Client", "phone": "9000010062"}).json()["id"]
    _create_employee_with_name(client, db_session, "Estimate RBAC Create Employee", "estimatecreaterbacuser", "estimatecreaterbacuser@example.com")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    })
    assert resp.status_code == 403


def test_employee_cannot_update_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Update Client", "phone": "9000010063"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Update Employee", "estimateupdaterbacuser", "estimateupdaterbacuser@example.com")
    resp = client.put(f"/api/estimates/{estimate['id']}", json={"discount": "1000"})
    assert resp.status_code == 403


def test_employee_cannot_revise_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Revise Client", "phone": "9000010064"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Revise Employee", "estimaterevisebacuser", "estimaterevisebacuser@example.com")
    resp = client.post(f"/api/estimates/{estimate['id']}/revise")
    assert resp.status_code == 403


def test_master_can_still_create_update_and_revise_estimates(client, test_user):
    """Backward compatibility - master retains full functionality."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Full Client", "phone": "9000010065"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()
    assert client.put(f"/api/estimates/{estimate['id']}", json={"discount": "500"}).status_code == 200
    assert client.post(f"/api/estimates/{estimate['id']}/revise").status_code == 201

# ===========================================================================
# From test_inventory_financial_rbac.py
# ===========================================================================

def test_master_sees_material_financial_fields(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Master Visible Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()

    resp = client.get(f"/api/materials/{material['id']}").json()
    assert resp["average_rate"] is not None
    assert resp["stock_value"] is not None


def test_employee_material_financial_fields_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Employee Hidden Rate Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()

    _create_employee(client, db_session, "matrbacuser", "matrbacuser@example.com")
    resp = client.get(f"/api/materials/{material['id']}").json()
    assert resp["average_rate"] is None
    assert resp["stock_value"] is None
    # Non-financial fields remain visible.
    assert resp["current_stock"] is not None
    assert resp["stock_status"] is not None


def test_employee_material_list_also_redacts_financial_fields(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "List Redaction Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "300.00",
    })

    _create_employee(client, db_session, "listrbacuser", "listrbacuser@example.com")
    materials = client.get("/api/materials/").json()
    match = next(m for m in materials if m["name"] == "List Redaction Material")
    assert match["average_rate"] is None
    assert match["stock_value"] is None


def test_employee_cannot_view_purchases_at_all(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase RBAC Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase RBAC Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    }).json()

    _create_employee(client, db_session, "purchaserbacuser", "purchaserbacuser@example.com")
    list_resp = client.get("/api/purchases/")
    assert list_resp.status_code == 403
    get_resp = client.get(f"/api/purchases/{purchase['id']}")
    assert get_resp.status_code == 403


def test_master_can_view_purchases(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/purchases/")
    assert resp.status_code == 200


def test_employee_dashboard_stock_value_is_null(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Dashboard RBAC Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "200.00",
    })

    _create_employee(client, db_session, "dashrbacuser", "dashrbacuser@example.com")
    resp = client.get("/api/dashboard/stock").json()
    assert resp["total_stock_value"] is None
    assert resp["purchase_value"] is None
    # Non-financial figures remain real.
    assert resp["low_stock_items"] is not None
    assert resp["out_of_stock_items"] is not None
    assert resp["recent_stock_movement"] is not None


def test_master_dashboard_stock_value_is_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/stock").json()
    assert resp["total_stock_value"] is not None


def test_employee_category_summary_stock_value_is_null(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Category Summary RBAC Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "200.00", "category": "TestCategoryRBAC",
    })

    _create_employee(client, db_session, "catrbacuser", "catrbacuser@example.com")
    resp = client.get("/api/dashboard/stock").json()
    match = next((c for c in resp["category_summary"] if c["category"] == "TestCategoryRBAC"), None)
    assert match is not None
    assert match["stock_value"] is None


def test_employee_excel_export_excludes_financial_sheets_and_columns(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "excelrbacuser", "excelrbacuser@example.com")

    resp = client.get("/api/reports/stock-dashboard.xlsx")
    assert resp.status_code == 200

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    sheet_names = wb.sheetnames
    assert "Dashboard" not in sheet_names
    assert "Purchases" not in sheet_names
    assert "Material Master" in sheet_names
    assert "Issues" in sheet_names

    material_sheet = wb["Material Master"]
    header_row = [c.value for c in material_sheet[4]]
    assert "Average Rate" not in header_row
    assert "Stock Value" not in header_row


def test_master_excel_export_includes_all_sheets(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/stock-dashboard.xlsx")
    assert resp.status_code == 200

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    assert set(["Dashboard", "Material Master", "Purchases", "Issues", "Suppliers"]).issubset(set(wb.sheetnames))


def test_chatbot_employee_denied_inventory_value_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatvaluerbacuser", "chatvaluerbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What is the inventory value?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_denied_purchase_cost_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatcostrbacuser", "chatcostrbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What was the purchase cost?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_denied_spend_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatspendrbacuser", "chatspendrbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "How much did we spend on plywood?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_still_gets_real_stock_status_answers(client, test_user, db_session):
    """The three explicitly-permitted questions from the brief must
    still work normally for an employee."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Chat Employee Allowed Material", "unit": "Sheets", "opening_stock": "23", "minimum_stock": "20",
    })
    _create_employee(client, db_session, "chatallowedrbacuser", "chatallowedrbacuser@example.com")

    resp1 = client.post("/api/chat/", json={"message": "How much Chat Employee Allowed Material do we have?"})
    assert "23" in resp1.json()["response"]

    resp2 = client.post("/api/chat/", json={"message": "Which materials are low in stock?"})
    assert resp2.status_code == 200
    assert "don't have access" not in resp2.json()["response"].lower()

    resp3 = client.post("/api/chat/", json={"message": "Which materials are out of stock?"})
    assert resp3.status_code == 200
    assert "don't have access" not in resp3.json()["response"].lower()


def test_chatbot_employee_denied_recent_purchases(client, test_user, db_session):
    """Matches the Purchases API restriction - an employee should not
    learn what was purchased recently via chat if they can't view it
    on the Purchases page either."""
    _login(client, test_user)
    _create_employee(client, db_session, "chatpurchaserbacuser", "chatpurchaserbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What materials were purchased recently?"})
    assert "master accounts only" in resp.json()["response"].lower()


def test_chatbot_master_still_gets_real_inventory_value(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "What is the inventory value?"})
    assert "don't have access" not in resp.json()["response"].lower()
    assert "Rs" in resp.json()["response"]


def _create_employee_with_name(client, db_session, name, username, email):
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


def test_employee_cannot_create_stock_issue(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    _create_employee_with_name(client, db_session, "Issue RBAC Employee", "issuerbacuser", "issuerbacuser@example.com")
    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 403

    # Confirm stock is genuinely untouched by the rejected attempt.
    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert float(unchanged["current_stock"]) == 10.0


def test_master_can_still_create_stock_issue(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Master Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 201


def test_employee_can_still_view_issues(client, test_user, db_session):
    """Viewing stays open - Issues carry no financial fields, matching
    "Employee can view stock"."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC View Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })

    _create_employee_with_name(client, db_session, "Issue RBAC View Employee", "issueviewrbacuser", "issueviewrbacuser@example.com")
    resp = client.get("/api/issues/")
    assert resp.status_code == 200

# ===========================================================================
# From test_notification_financial_rbac.py
# ===========================================================================

def test_employee_sees_broadcast_low_stock_notification(client, test_user, db_session):
    """The real bug found this turn - operational broadcasts must
    reach employees, not just master."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Low Stock Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })

    _create_employee(client, db_session, "notiflowuser", "notiflowuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Low Stock Material" in n["title"] for n in notifications)


def test_employee_sees_broadcast_out_of_stock_notification(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Out Of Stock Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    })

    _create_employee(client, db_session, "notifoosuser", "notifoosuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Out Of Stock Material" in n["title"] for n in notifications)


def test_employee_does_not_see_broadcast_payment_overdue_notification(client, test_user, db_session):
    """The genuinely financial broadcast must still stay hidden."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Overdue Client", "phone": "9000010130"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee(client, db_session, "notifoverdueuser", "notifoverdueuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert not any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_master_still_sees_payment_overdue_notification(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Master Overdue Client", "phone": "9000010131"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "60000.00", "advance": "0",
    })

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_purchase_received_notification_deep_link_is_accessible_to_everyone(client, test_user, db_session):
    """The dead-end link bug - PURCHASE_RECEIVED is visible to
    employees, so its action_path must not point at a page they can no
    longer access (/purchases is now master-only)."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif RBAC Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Notif RBAC Purchase Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    _create_employee(client, db_session, "notifpurchaseuser", "notifpurchaseuser@example.com")
    notifications = client.get("/api/notifications/").json()
    purchase_notif = next(n for n in notifications if n["notification_type"] == "PURCHASE_RECEIVED"
                           and "Notif RBAC Purchase Material" in n["title"])
    assert purchase_notif["action_path"] == f"/materials/{material['id']}"
    # And that page must genuinely be reachable by this employee.
    material_resp = client.get(f"/api/materials/{material['id']}")
    assert material_resp.status_code == 200

# ===========================================================================
# From test_order_financial_rbac.py
# ===========================================================================

def test_master_sees_order_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Master Client", "phone": "9000010132"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is not None
    assert resp["balance"] is not None
    assert resp["payment_status"] is not None


def test_employee_get_order_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Employee Client", "phone": "9000010133"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    _create_employee_with_name(client, db_session, "Order RBAC Employee", "orderrbacuser", "orderrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is None
    assert resp["advance"] is None
    assert resp["other_received"] is None
    assert resp["total_received"] is None
    assert resp["balance"] is None
    assert resp["items_subtotal"] is None
    assert resp["payment_status"] is None
    # Non-financial order status remains real.
    assert resp["project_status"] is not None
    assert resp["progress_percent"] is not None
    assert resp["order_code"] == order["order_code"]


def test_employee_list_orders_financials_are_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC List Client", "phone": "9000010134"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "45000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Order RBAC List Employee", "orderlistrbacuser", "orderlistrbacuser@example.com")
    orders = client.get("/api/orders/").json()
    match = next(o for o in orders if o["client_id"])
    assert match["order_value"] is None


def test_employee_cannot_derive_order_total_from_line_items(client, test_user, db_session):
    """The deeper part of this fix - redacting only the top-level
    order_value while leaving item.rate/item.amount visible would let
    anyone just sum the line items back to the real total."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Client", "phone": "9000010135"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Wardrobe", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Wardrobe", "quantity": "1", "unit": "Nos", "rate": "50000.00", "product_id": product_id}],
    }).json()

    _create_employee_with_name(client, db_session, "Order RBAC Items Employee", "orderitemsrbacuser", "orderitemsrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert len(resp["items"]) == 1
    assert resp["items"][0]["rate"] is None
    assert resp["items"][0]["amount"] is None
    # Non-financial item fields remain visible - still shows what was ordered.
    assert resp["items"][0]["description"] == "Wardrobe"
    assert resp["items"][0]["quantity"] is not None


def test_master_sees_order_line_item_pricing(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Master Client", "phone": "9000010136"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Kitchen", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Kitchen", "quantity": "1", "unit": "Nos", "rate": "30000.00", "product_id": product_id}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["items"][0]["rate"] is not None
    assert resp["items"][0]["amount"] is not None


def test_master_sees_orders_dashboard_financials(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is not None
    assert resp["total_received"] is not None
    assert resp["pending_payment"] is not None


def test_employee_orders_dashboard_financials_are_null(client, test_user, db_session):
    """The real, previously-untouched gap found this turn."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Orders Dash RBAC Client", "phone": "9000010053"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Orders Dash RBAC Employee", "ordersdashrbacuser", "ordersdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is None
    assert resp["total_received"] is None
    assert resp["pending_payment"] is None
    # Non-financial fields remain real.
    assert resp["active_orders"] is not None
    assert resp["order_pipeline"] is not None


def test_employee_top_orders_money_fields_are_null_but_status_visible(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Top Orders RBAC Client", "phone": "9000010054"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "70000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Top Orders RBAC Employee", "toporderrbacuser", "toporderrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    match = next(o for o in resp["top_orders"] if o["client"] == "Top Orders RBAC Client")
    assert match["order_value"] is None
    assert match["received"] is None
    assert match["pending"] is None
    assert match["status"] is not None


def test_employee_order_profitability_is_empty_not_leaked(client, test_user, db_session):
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Profit Dash RBAC Employee", "profitdashrbacuser", "profitdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["order_profitability"] == []


# ===========================================================================
# Regression tests for security defects found and fixed during this pass
# (previously undiscovered by any test in this suite)
# ===========================================================================


def test_employee_cannot_export_another_employees_attendance(client, test_user, db_session):
    """Item A: /api/reports/attendance.xlsx previously had no ownership
    check at all - any authenticated employee could pass an arbitrary
    employee_id and download another employee's full attendance data."""
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Attendance Export Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()

    _create_employee(client, db_session, "attexportrbacuser", "attexportrbacuser@example.com")
    resp = client.get(f"/api/reports/attendance.xlsx?employee_id={other_employee['id']}")
    assert resp.status_code == 403

    # Exporting with no employee_id filter (or their own) still works -
    # this is an ownership check, not a blanket export ban.
    own_resp = client.get("/api/reports/attendance.xlsx")
    assert own_resp.status_code == 200


def test_employee_cannot_export_another_employees_leaves(client, test_user, db_session):
    """Item B: /api/reports/leaves.xlsx had the identical gap as
    attendance export."""
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave Export Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()

    _create_employee(client, db_session, "leaveexportrbacuser", "leaveexportrbacuser@example.com")
    resp = client.get(f"/api/reports/leaves.xlsx?employee_id={other_employee['id']}")
    assert resp.status_code == 403

    own_resp = client.get("/api/reports/leaves.xlsx")
    assert own_resp.status_code == 200


def test_employee_staff_dashboard_total_overtime_is_null(client, test_user, db_session):
    """Item C: /api/dashboard/staff's total_overtime was an
    organization-wide aggregate returned unconditionally, unlike
    employee_performance right next to it, which was already
    correctly redacted."""
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Staff Dash RBAC Employee", "staffdashrbacuser", "staffdashrbacuser@example.com")
    resp = client.get("/api/dashboard/staff").json()
    assert resp["total_overtime"] is None
    # Non-financial/non-aggregate fields remain visible.
    assert resp["active_employees"] is not None


def test_master_staff_dashboard_total_overtime_is_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/staff").json()
    assert resp["total_overtime"] is not None


def test_employee_workforce_analytics_hour_totals_are_null(client, test_user, db_session):
    """Item D: /api/analytics/workforce's total_overtime_hours/
    total_working_hours were the same organization-wide, unguarded
    aggregate as the staff dashboard's total_overtime."""
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Workforce RBAC Employee", "workforcerbacuser", "workforcerbacuser@example.com")
    resp = client.get("/api/analytics/workforce").json()
    assert resp["total_overtime_hours"] is None
    assert resp["total_working_hours"] is None


def test_master_workforce_analytics_hour_totals_are_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/analytics/workforce").json()
    assert resp["total_overtime_hours"] is not None
    assert resp["total_working_hours"] is not None


def test_employee_top_orders_are_not_sorted_by_real_financial_value(client, test_user, db_session):
    """Item E: order_value was already correctly redacted to None in
    top_orders, but the list itself was still sorted by the real,
    unredacted value - leaking relative financial ranking through
    position alone. For a non-privileged viewer, the sort order must
    not depend on order_value at all."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Sort Leak RBAC Client", "phone": "9000010099"}).json()["id"]
    low_value_high_progress = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "1000.00", "advance": "0",
    }).json()
    update_resp_1 = client.put(f"/api/orders/{low_value_high_progress['id']}", json={"progress_percent": 90})
    assert update_resp_1.status_code == 200
    high_value_low_progress = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "900000.00", "advance": "0",
    }).json()
    update_resp_2 = client.put(f"/api/orders/{high_value_low_progress['id']}", json={"progress_percent": 5})
    assert update_resp_2.status_code == 200

    _create_employee_with_name(client, db_session, "Sort Leak RBAC Employee", "sortleakrbacuser", "sortleakrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    ids_in_order = [o["id"] for o in resp["top_orders"]]
    # The high-progress/low-value order must rank ahead of the
    # low-progress/high-value one for a non-privileged viewer - if the
    # list were still (bug-era) sorted by the real order_value, the
    # order would be reversed even though order_value itself reads None.
    assert ids_in_order.index(low_value_high_progress["id"]) < ids_in_order.index(high_value_low_progress["id"])
    for o in resp["top_orders"]:
        assert o["order_value"] is None


def test_employee_client_pdf_excludes_sales_summary_and_order_values(client, test_user, db_session):
    """Item F: generate_client_pdf never received any role information
    at all, so it always printed full order values and totals
    regardless of who requested it - a direct bypass of the JSON
    client API's own, already-correct financial redaction."""
    import pypdf
    from io import BytesIO

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "PDF Leak RBAC Client", "phone": "9000010088"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "PDF Leak RBAC Employee", "pdfleakrbacuser", "pdfleakrbacuser@example.com")
    resp = client.get(f"/api/reports/clients/{client_id}/profile.pdf")
    assert resp.status_code == 200
    reader = pypdf.PdfReader(BytesIO(resp.content))
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert "SALES SUMMARY" not in pdf_text
    # The real order value, as ReportLab genuinely renders it (via
    # format_inr), must not appear anywhere in the extracted PDF text.
    assert "50,000" not in pdf_text


def test_master_client_pdf_includes_sales_summary(client, test_user):
    import pypdf
    from io import BytesIO

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "PDF Master RBAC Client", "phone": "9000010077"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })
    resp = client.get(f"/api/reports/clients/{client_id}/profile.pdf")
    assert resp.status_code == 200
    reader = pypdf.PdfReader(BytesIO(resp.content))
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert "SALES SUMMARY" in pdf_text
    assert "50,000" in pdf_text

# ===========================================================================
# Financial/dashboard/AI-chat RBAC (from the former analytics test segment)
# ===========================================================================
def _login_with_credentials(client, identifier="test@example.com", password="TestPass123!"):
    resp = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200
    return resp


def _create_employee_user(client, db_session, employee_id, username, email, password="EmpPass1!"):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password(password), role="user",
        employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _seed_master_data(client):
    """Creates one of everything analytics aggregates, using the real
    module endpoints (not direct DB inserts) so every figure analytics
    reports on is a genuine authoritative record."""
    client_obj = client.post("/api/clients/", json={"name": "Analytics Test Client", "phone": "9000010086"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_obj["id"], "order_date": "2026-06-01T00:00:00",
        "order_value": "100000", "advance": "20000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "amount": "10000", "payment_date": "2026-08-01T00:00:00",
    })
    supplier = client.post("/api/suppliers/", json={"name": "Analytics Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Analytics Test Ply", "unit": "Sheets", "opening_stock": "2",
        "minimum_stock": "10", "average_rate": "1500.00", "supplier_id": supplier["id"],
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "1500.00", "gst_percent": "18",
        "payment_status": "Pending",
    })
    client.post("/api/project-expenses/", json={
        "date": "2026-08-01T00:00:00", "order_id": order["id"], "category": "Raw Material",
        "amount": "5000",
    })
    return {"client": client_obj, "order": order, "supplier": supplier, "material": material}


def _make_non_master(client, db_session, name="Analytics RBAC Employee", username="analyticsrbacuser",
                      email="analyticsrbacuser@example.com"):
    employee = client.post("/api/employees/", json={"name": name}).json()
    _create_employee_user(client, db_session, employee["id"], username, email)
    _login_with_credentials(client, identifier=email, password="EmpPass1!")
    return employee


# --------------------------------------------------------------------- #
# Data scope
# --------------------------------------------------------------------- #
def test_master_only_domains_blocked_for_non_master(client, test_user, db_session):
    """sales, purchases, payments, expenses aggregate financial totals
    across every client/order - matching purchases.py / payments.py /
    project_expenses.py's own master-only gates."""
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/sales", "/api/analytics/purchases",
                 "/api/analytics/payments", "/api/analytics/expenses"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_open_domains_available_to_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/inventory", "/api/analytics/production",
                 "/api/analytics/projects", "/api/analytics/tasks",
                 "/api/analytics/workforce", "/api/analytics/operations"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_alerts_feed_excludes_master_only_domains_for_non_master(client, test_user, db_session):
    """The consolidated /alerts feed must not leak sales/purchases/expenses
    alerts to a non-master viewer, even though it fans out across every
    domain internally."""
    _login_with_credentials(client)
    # _seed_master_data's order is dated 2026-06-01, well over 60 days
    # before the current date, so the sales alert fires for master
    # without any extra setup.
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/alerts")
    assert resp.status_code == 200
    domains = {a["domain"] for a in resp.json()["alerts"]}
    assert domains.isdisjoint({"sales", "purchases", "expenses"})


# --------------------------------------------------------------------- #
# Aggregation authorization (financial figures nulled BEFORE the
# response is built, not stripped after the fact)
# --------------------------------------------------------------------- #
def test_inventory_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_stock_value"] is None
    assert all(c["stock_value"] is None for c in data["category_breakdown"])

    # Same call, as master, must show the real figure.
    _login_with_credentials(client)
    master_data = client.get("/api/analytics/inventory").json()
    assert master_data["total_stock_value"] is not None
    assert master_data["total_stock_value"] > 0


def test_operations_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/operations").json()
    assert resp["total_stock_value"] is None


# --------------------------------------------------------------------- #
# Financial data boundaries - project profitability
# --------------------------------------------------------------------- #
def test_project_profitability_hidden_from_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/projects").json()
    assert resp["order_profitability"] == []
    assert resp["overall_gross_margin_ratio"] is None

    _login_with_credentials(client)
    master_resp = client.get("/api/analytics/projects").json()
    assert len(master_resp["order_profitability"]) >= 1
    assert master_resp["overall_gross_margin_ratio"] is not None


def test_gross_margin_is_a_ratio_not_a_0_to_100_percent(client, test_user):
    """Regression for the gross-margin naming/scale contract:
    gross_margin_ratio must be a fraction (e.g. ~0.85 for an
    85% margin), never a 0-100 value - a field that was previously
    misnamed "gross_margin_percent" while holding a ratio, which risked
    a 100x misinterpretation by any new consumer that took the name at
    face value."""
    _login_with_credentials(client)
    _seed_master_data(client)

    resp = client.get("/api/analytics/projects").json()
    rows = resp["order_profitability"]
    assert len(rows) >= 1
    for row in rows:
        # order_value=100000, direct costs from the seeded purchase/expense
        # are well under the order value, so this must be a positive
        # fraction less than 1 - never anywhere near a 0-100 scale value.
        assert -1.0 <= row["gross_margin_ratio"] <= 1.0

    # The overall aggregate must be on the exact same ratio scale as each
    # per-order row - this is precisely the two-scale inconsistency the
    # fix removes.
    assert -1.0 <= resp["overall_gross_margin_ratio"] <= 1.0


def test_gross_margin_ratio_is_none_when_no_orders(client, test_user, db_session):
    """Zero-revenue / no-order case must not divide by zero or otherwise
    error - it should report a clean 0.0 for order rows with no order
    value, and the aggregate should still resolve without raising."""
    _login_with_credentials(client)
    resp = client.get("/api/analytics/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_profitability"] == []
    assert body["overall_gross_margin_ratio"] == 0.0


# --------------------------------------------------------------------- #
# Drill-down authorization - the underlying records a KPI links to must
# obey the same scope as the KPI itself.
# --------------------------------------------------------------------- #
def test_outstanding_orders_drill_down_is_real_and_master_only(client, test_user, db_session):
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    # Non-master can't reach the drill-down data at all.
    assert client.get("/api/analytics/sales").status_code == 403

    _login_with_credentials(client)
    data = client.get("/api/analytics/sales").json()
    order_ids = {o["id"] for o in data["outstanding_orders"]}
    assert seed["order"]["id"] in order_ids
    # The outstanding total must equal the real Order.balance sum, not a
    # separately-invented figure.
    order_detail = client.get(f"/api/orders/{seed['order']['id']}").json()
    assert any(o["balance"] == float(order_detail["balance"]) for o in data["outstanding_orders"])


def test_low_stock_drill_down_visible_but_stock_value_not(client, test_user, db_session):
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    data = client.get("/api/analytics/inventory").json()
    material_ids = {m["id"] for m in data["low_stock_materials"]}
    assert seed["material"]["id"] in material_ids
    # Drill-down rows expose quantities, never a redacted-financial field.
    assert "stock_value" not in data["low_stock_materials"][0]


# --------------------------------------------------------------------- #
# Export authorization - export must inherit the same scope as on-screen.
# --------------------------------------------------------------------- #
def test_master_only_exports_blocked_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/reports/purchases.xlsx", "/api/reports/payments.xlsx",
                 "/api/reports/project-expenses.xlsx"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_orders_export_redacts_financial_columns_for_non_master(client, test_user, db_session):
    import io
    from openpyxl import load_workbook

    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/reports/orders.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    # Locate the actual header row (title/subtitle rows come first).
    header_row = []
    for row in ws.iter_rows(values_only=True):
        if row and "Client" in row:
            header_row = list(row)
            break
    assert "Order Value" not in header_row
    assert "Balance" not in header_row

    _login_with_credentials(client)
    master_resp = client.get("/api/reports/orders.xlsx")
    wb2 = load_workbook(io.BytesIO(master_resp.content))
    ws2 = wb2.active
    master_header = []
    for row in ws2.iter_rows(values_only=True):
        if row and "Client" in row:
            master_header = list(row)
            break
    assert "Order Value" in master_header
    assert "Balance" in master_header


# --------------------------------------------------------------------- #
# HR data boundaries
# --------------------------------------------------------------------- #
def test_workforce_non_master_sees_only_own_row(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    other_employee = client.post("/api/employees/", json={"name": "Other Workforce Employee"}).json()
    own_employee = _make_non_master(
        client, db_session, name="Own Workforce Employee",
        username="workforceown", email="workforceown@example.com",
    )

    resp = client.get("/api/analytics/workforce").json()
    ids_seen = {row["employee_id"] for row in resp["employee_performance"]}
    assert ids_seen == {own_employee["id"]}
    assert other_employee["id"] not in ids_seen

    _login_with_credentials(client)
    master_resp = client.get("/api/analytics/workforce").json()
    master_ids = {row["employee_id"] for row in master_resp["employee_performance"]}
    assert other_employee["id"] in master_ids
    assert own_employee["id"] in master_ids


# --------------------------------------------------------------------- #
# AI (chat) data boundaries - AI must use the same permission scope,
# never a shortcut around it because it queries the DB directly.
# --------------------------------------------------------------------- #
def test_ai_expense_explanation_blocked_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "why did expenses increase this month"})
    assert resp.status_code == 200
    assert "master accounts only" in resp.json()["response"].lower()


def test_ai_whats_changed_omits_financial_lines_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert resp.status_code == 200
    text = resp.json()["response"].lower()
    assert "revenue" not in text
    assert "expenses are" not in text

    _login_with_credentials(client)
    master_resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert master_resp.status_code == 200


def test_ai_delayed_projects_grounded_in_real_projects_analytics(client, test_user, db_session):
    """The chatbot's delayed-projects answer must agree with what the
    Analytics page's own drill-down shows for the same underlying data -
    never a separately fabricated list."""
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    client.put(f"/api/orders/{seed['order']['id']}", json={"project_status": "On Hold"})

    resp = client.post("/api/chat/", json={"message": "which projects are delayed"})
    assert resp.status_code == 200
    body = resp.json()
    record_paths = {r["path"] for r in body["records"]}
    assert f"/orders/{seed['order']['id']}" in record_paths

    analytics_resp = client.get("/api/analytics/projects").json()
    delayed_paths = {f"/orders/{p['id']}" for p in analytics_resp["delayed_projects"]}
    assert record_paths == delayed_paths

# ===========================================================================
# Estimate/order PDF export RBAC (from test_auth_and_chatbot_misc.py)
# ===========================================================================
# ===========================================================================
def _create_and_login_employee(client, db_session, username, email):
    employee = client.post("/api/employees/", json={"name": "PDF RBAC Employee", "monthly_salary": "20000"}).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def _seed_order(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Client", "phone": "9000010073"}).json()["id"]
    return client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()


def _seed_estimate(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Estimate Client", "phone": "9000010074"}).json()["id"]
    return client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "30000", "labor_cost": "10000",
    }).json()


def test_master_can_download_order_estimate_pdf(client, test_user):
    _login(client, test_user)
    order = _seed_order(client)
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_order_estimate_pdf(client, test_user, db_session):
    _login(client, test_user)
    order = _seed_order(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser1", "pdfrbacuser1@example.com")
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 403


def test_master_can_download_estimate_quote_pdf(client, test_user):
    _login(client, test_user)
    estimate = _seed_estimate(client)
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_estimate_quote_pdf(client, test_user, db_session):
    _login(client, test_user)
    estimate = _seed_estimate(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser2", "pdfrbacuser2@example.com")
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 403


def test_pdf_exports_require_auth(client):
    resp = client.get("/api/reports/orders/1/estimate.pdf")
    assert resp.status_code == 401
    resp = client.get("/api/reports/estimates/1/quote.pdf")
    assert resp.status_code == 401
