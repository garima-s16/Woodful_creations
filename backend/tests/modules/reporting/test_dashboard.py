"""Tests for /api/dashboard/* - the overview widgets. overall_gross_margin_ratio
specifically: a true aggregate across every order, not derived from the
top-orders sample also returned here (which is deliberately bounded to
10) - see OrderService.overall_gross_margin's own docstring for why
those must be two different calculations."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _create_order_with_costs(client, name_suffix, order_value="20000.00"):
    client_id = client.post("/api/clients/", json={
        "name": f"Dashboard Margin Test Client {name_suffix}", "phone": f"90000101{name_suffix}",
    }).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": order_value, "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": f"Dashboard Margin Test Material {name_suffix}", "unit": "Sheets",
        "opening_stock": "10", "minimum_stock": "1", "average_rate": "500.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "4", "unit": "Sheets",
    })
    return order


def test_overall_gross_margin_ratio_is_a_true_aggregate_not_a_sample(client, test_user):
    """The core regression this field exists to prevent: with more
    orders than the top-orders list holds (10), the aggregate must
    still reflect ALL of them, not just the sampled subset."""
    _login(client, test_user)
    orders = [_create_order_with_costs(client, str(i)) for i in range(12)]
    assert len(orders) == 12

    resp = client.get("/api/dashboard/orders").json()
    assert len(resp["top_orders"]) <= 10  # confirms the sample really is bounded
    assert resp["overall_gross_margin_ratio"] is not None
    # order_value=20000, material_cost=4*500=2000, no other expenses ->
    # gross profit 18000 on this order; every seeded order here is
    # identical, so the aggregate ratio must equal any single order's.
    assert abs(resp["overall_gross_margin_ratio"] - 0.9) < 0.01


def test_overall_gross_margin_ratio_is_none_for_non_master(client, test_user, db_session):
    _login(client, test_user)
    _create_order_with_costs(client, "1")

    employee = User(
        username="dashboardmarginuser", email="dashboardmarginuser@example.com", full_name="Dashboard Margin User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "dashboardmarginuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/dashboard/orders").json()
    assert resp["overall_gross_margin_ratio"] is None
    assert resp["order_profitability"] == []


def test_overall_gross_margin_ratio_is_zero_when_no_orders(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/orders").json()
    assert resp["overall_gross_margin_ratio"] == 0.0
