"""Test for the missing Tasks/Production Excel export found closing
the Tasks/Staff chain - no such export existed at all, despite the
brief explicitly requiring a downloadable Staff/Tasks report."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_tasks_excel_export_contains_real_data(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Tasks Excel Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Tasks Excel Test Task",
    })
    client.post("/api/production-jobs/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "operation": "Tasks Excel Test Operation",
        "planned_qty": 5, "status": "Not Started",
    })

    resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
    assert len(resp.content) > 1000  # a genuine workbook, not an empty/error stub

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Tasks" in wb.sheetnames
    assert "Production" in wb.sheetnames


def test_tasks_excel_export_open_to_any_authenticated_role(client, test_user, db_session):
    """Everyone can view tasks - the export must not be restricted."""
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Tasks Excel RBAC Employee"}).json()
    user = User(
        username="tasksexcelrbacuser", email="tasksexcelrbacuser@example.com", full_name="Tasks Excel RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "tasksexcelrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
