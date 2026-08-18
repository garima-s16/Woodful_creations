"""Regression tests for the N+1 query bugs found and fixed across
every Excel export (Section 15 - "avoid repeated database queries").
Counts real SQL statements executed during each export via a SQLAlchemy
event listener, rather than just checking the export still succeeds -
a passing-but-slow export would hide the exact bug this is guarding
against."""
from sqlalchemy import event
from tests.conftest import engine


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


class _QueryCounter:
    def __init__(self):
        self.count = 0

    def __enter__(self):
        event.listen(engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, *args):
        event.remove(engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1


def test_tasks_export_query_count_does_not_scale_with_row_count(client, test_user):
    """The core N+1 regression guard - export a growing number of
    tasks, each with a DIFFERENT employee and order, and confirm the
    query count stays bounded rather than growing linearly."""
    _login(client, test_user)
    for i in range(8):
        client_id = client.post("/api/clients/", json={"name": f"N+1 Test Client {i}"}).json()["id"]
        order = client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "10000", "advance": "0",
        }).json()
        employee = client.post("/api/employees/", json={"name": f"N+1 Test Employee {i}"}).json()
        client.post("/api/daily-tasks/", json={
            "date": "2026-08-21T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
            "task_description": f"N+1 test task {i}",
        })

    with _QueryCounter() as counter:
        resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
    # With 8 distinct employees/orders, an N+1 bug would need roughly
    # 8 (tasks) + 8 (employee lookups) + 8 (order lookups) = 24+ queries
    # for this one export alone. Eager-loading keeps it to a small,
    # fixed number regardless of row count.
    assert counter.count < 15, f"expected a bounded query count, got {counter.count} - possible N+1 regression"


def test_purchases_export_query_count_does_not_scale_with_row_count(client, test_user):
    _login(client, test_user)
    for i in range(8):
        supplier = client.post("/api/suppliers/", json={"name": f"N+1 Purchase Supplier {i}"}).json()
        material = client.post("/api/materials/", json={
            "name": f"N+1 Purchase Material {i}", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
        }).json()
        client.post("/api/purchases/", json={
            "date": "2026-08-21T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        })

    with _QueryCounter() as counter:
        resp = client.get("/api/reports/purchases.xlsx")
    assert resp.status_code == 200
    assert counter.count < 15, f"expected a bounded query count, got {counter.count} - possible N+1 regression"
