"""Family 21 - "Provide a safe development/demo reset" +
"Restarting must not duplicate records" (seeding idempotency)."""
from app.core.security import hash_password
from app.models.user import User
from app.models.client import Client
from app.models.product import Product
from app.models.order import Order
from app.models.order_item import OrderItem


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_reset_requires_master_role(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Reset RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(username="resetrbacuser", email="resetrbacuser@example.com", full_name="Reset RBAC Employee",
                password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "resetrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/demo/reset")
    assert resp.status_code == 403


def test_reset_blocked_in_production(client, test_user, monkeypatch):
    from app.core.config import settings
    _login(client, test_user)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 403
    assert "production" in resp.json()["detail"].lower()


def test_reset_clears_and_reseeds_demo_data(client, test_user, db_session):
    _login(client, test_user)
    # Create some throwaway data first, distinct from what the seed
    # itself creates, to prove reset genuinely clears the table rather
    # than merely re-running the idempotent seed on top of it.
    client.post("/api/clients/", json={"name": "Pre-Reset Throwaway Client"})

    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reset_complete"

    # The throwaway client is gone...
    remaining_names = [c["name"] for c in client.get("/api/clients/").json()]
    assert "Pre-Reset Throwaway Client" not in remaining_names
    # ...and the environment is genuinely reseeded with real, interconnected data.
    assert db_session.query(Client).count() > 0
    assert db_session.query(Product).count() > 0
    assert db_session.query(Order).count() > 0
    assert db_session.query(OrderItem).count() > 0


def test_reset_is_idempotent_no_duplicate_records_on_repeat(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/demo/reset")
    first_counts = {
        "clients": db_session.query(Client).count(),
        "products": db_session.query(Product).count(),
        "orders": db_session.query(Order).count(),
        "order_items": db_session.query(OrderItem).count(),
    }

    client.post("/api/demo/reset")
    second_counts = {
        "clients": db_session.query(Client).count(),
        "products": db_session.query(Product).count(),
        "orders": db_session.query(Order).count(),
        "order_items": db_session.query(OrderItem).count(),
    }
    assert first_counts == second_counts


def test_seeding_directly_twice_never_duplicates(db_session):
    """Exercises run_seed() itself (not just the HTTP endpoint) -
    calling it twice against the same session must be a safe no-op the
    second time."""
    from scripts.seed_sample_data import run_seed

    run_seed(db_session)
    first_count = db_session.query(Product).count()
    assert first_count > 0

    run_seed(db_session)
    second_count = db_session.query(Product).count()
    assert first_count == second_count
