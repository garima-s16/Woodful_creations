from tests.helpers import _login


"""End-to-end integration test for the full business chain the product
brief specifies: Client -> Estimate -> Order -> Payment -> Material ->
Purchase -> Material Issue -> Task -> Production. Verifies that records
created at each step actually cross-reference each other correctly -
not just that each endpoint works in isolation, but that the DATA
connects the way a real business workflow needs it to.
"""


def test_full_business_journey_stays_correctly_linked(client, test_user):
    _login(client, test_user)

    # 1. CLIENT
    client_resp = client.post("/api/clients/", json={
        "name": "Journey Test Client", "phone": "9988776655", "email": "journey@example.com",
    })
    assert client_resp.status_code == 201
    the_client = client_resp.json()
    client_id = the_client["id"]
    assert the_client["business_id"] is not None

    # 2. ESTIMATE, linked to the client
    estimate_resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "200000.00", "labor_cost": "80000.00", "tax_percent": "18",
    })
    assert estimate_resp.status_code == 201
    estimate = estimate_resp.json()
    assert estimate["client_id"] == client_id
    assert estimate["total_cost"] == "330400.00"  # 200000 + 80000 = 280000, +18% tax = 330400

    # 3. ORDER, linked to the same client
    order_resp = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Living Room Set",
        "order_date": "2026-08-01T00:00:00", "order_value": "330400.00", "advance": "50000.00",
        "delivery_date": "2026-09-15T00:00:00",
    })
    assert order_resp.status_code == 201
    order = order_resp.json()
    order_id = order["id"]
    assert order["client_id"] == client_id
    assert order["balance"] == "280400.00"  # 330400 - 50000 advance

    # Client detail should now show this order in its stats.
    client_check = client.get(f"/api/clients/{client_id}")
    assert client_check.json()["total_orders"] >= 1

    # 4. PAYMENT, linked to the order (and therefore transitively to the client)
    payment_resp = client.post("/api/payments/", json={
        "date": "2026-08-10T00:00:00", "order_id": order_id,
        "payment_type": "Progress Payment", "payment_mode": "Bank", "amount": "100000.00",
    })
    assert payment_resp.status_code == 201
    payment = payment_resp.json()
    assert payment["order_id"] == order_id

    # The order's running balance must reflect the new payment.
    order_after_payment = client.get(f"/api/orders/{order_id}").json()
    assert order_after_payment["total_received"] == "150000.00"  # 50000 advance + 100000 payment
    assert order_after_payment["balance"] == "180400.00"  # 330400 - 150000

    # 5. MATERIAL
    material_resp = client.post("/api/materials/", json={
        "name": "Journey Test Teak Wood", "unit": "CFT", "opening_stock": 0, "minimum_stock": 10,
    })
    assert material_resp.status_code == 201
    material = material_resp.json()
    material_id = material["id"]

    # 6. PURCHASE, brings stock in
    purchase_resp = client.post("/api/purchases/", json={
        "date": "2026-08-05T00:00:00", "supplier_id": client.post("/api/suppliers/", json={
            "name": "Journey Test Timber Supplier"
        }).json()["id"],
        "material_id": material_id, "quantity": "50", "unit": "CFT", "rate": "3000.00",
        "gst_percent": "18", "payment_status": "Paid",
    })
    assert purchase_resp.status_code == 201

    material_after_purchase = client.get(f"/api/materials/{material_id}").json()
    assert material_after_purchase["current_stock"] == 50

    # 7. MATERIAL ISSUE, against the order, draws stock back down
    issue_resp = client.post("/api/issues/", json={
        "date": "2026-08-12T00:00:00", "order_id": order_id, "material_id": material_id,
        "quantity_issued": "20", "unit": "CFT",
    })
    assert issue_resp.status_code == 201
    issue = issue_resp.json()
    assert issue["order_id"] == order_id

    material_after_issue = client.get(f"/api/materials/{material_id}").json()
    assert material_after_issue["current_stock"] == 30  # 50 purchased - 20 issued

    # 8. EMPLOYEE + TASK, linked to the order
    employee_resp = client.post("/api/employees/", json={
        "name": "Journey Test Carpenter", "department": "Production",
        "monthly_salary": "22000", "daily_wage": "900",
    })
    assert employee_resp.status_code == 201
    employee_id = employee_resp.json()["id"]

    task_resp = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "order_id": order_id,
        "task_description": "Assemble living room set frame",
    })
    assert task_resp.status_code == 201
    assert task_resp.json()["order_id"] == order_id
    assert task_resp.json()["employee_id"] == employee_id

    # 9. PRODUCTION JOB, linked to the order and the material used
    job_resp = client.post("/api/production-jobs/", json={
        "date": "2026-08-14T00:00:00", "order_id": order_id, "material_id": material_id,
        "employee_id": employee_id, "operation": "Assembly", "planned_qty": 1,
    })
    assert job_resp.status_code == 201
    assert job_resp.json()["order_id"] == order_id

    # 10. DASHBOARD aggregates must reflect this whole chain, not just
    #     the individual endpoints - this is the actual integration
    #     check: does the data reachable from a *different* endpoint
    #     (the dashboard) agree with what was just built.
    stock_dash = client.get("/api/dashboard/stock").json()
    assert stock_dash["total_stock_value"] > 0

    orders_dash = client.get("/api/dashboard/orders").json()
    assert orders_dash["pending_payment"] >= 180400.0

    # 11. SEARCH must find the order by both its sequential code and its
    #     opaque business_id, and the client by name.
    search_by_code = client.get("/api/search/", params={"q": order["order_code"]}).json()
    assert any(r["id"] == order_id and r["type"] == "Order" for r in search_by_code)

    search_by_business_id = client.get("/api/search/", params={"q": order["business_id"]}).json()
    assert any(r["id"] == order_id and r["type"] == "Order" for r in search_by_business_id)

    search_by_client_name = client.get("/api/search/", params={"q": "Journey Test Client"}).json()
    assert any(r["id"] == client_id and r["type"] == "Client" for r in search_by_client_name)

    # 12. The chatbot, asked about this specific order via context, must
    #     reflect the real current state - not a stale or generic answer.
    chat_resp = client.post("/api/chat/", json={
        "message": "summarize this order", "context": {"order_id": order_id},
    })
    assert chat_resp.status_code == 200
    chat_text = chat_resp.json()["response"]
    assert order["order_code"] in chat_text
    assert "Journey Test Client" in chat_text
