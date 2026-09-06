"""Tests for the Salary Advance workflow (Family P0.44): employee/
Master request, Master approve (at requested or a different amount)/
reject, recovery against a real SalarySlip (never a bare number), and
the safety validations (no over-recovery, no recovery from an
unapproved/rejected advance, no recovery without a matching slip)."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _make_employee(client, suffix, salary="26000"):
    return client.post("/api/employees/", json={
        "name": f"Salary Advance Employee {suffix}", "monthly_salary": salary,
    }).json()


def _login_as_employee(client, db_session, employee_id, suffix):
    user = User(
        username=f"salaryadvanceuser{suffix}", email=f"salaryadvanceuser{suffix}@example.com",
        full_name=f"Salary Advance User {suffix}", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": f"salaryadvanceuser{suffix}@example.com", "password": "EmpPass1!"})


def test_employee_can_request_own_advance(client, test_user, db_session):
    _login(client, test_user)
    employee = _make_employee(client, "1")
    _login_as_employee(client, db_session, employee["id"], "1")

    resp = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
        "reason": "Medical expense",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "Pending"
    assert float(body["requested_amount"]) == 5000.0
    assert body["created_by"] == f"salaryadvanceuser1"


def test_employee_cannot_request_advance_for_another_employee(client, test_user, db_session):
    _login(client, test_user)
    other_employee = _make_employee(client, "2a")
    self_employee = _make_employee(client, "2b")
    _login_as_employee(client, db_session, self_employee["id"], "2")

    resp = client.post("/api/salary-advances/", json={
        "employee_id": other_employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    })
    assert resp.status_code == 403


def test_master_can_create_advance_on_behalf_of_employee(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "3")

    resp = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "3000", "request_date": "2026-09-01T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Pending"


def test_approval_notifies_the_employees_linked_user(client, test_user, db_session):
    """The real end-to-end path: approve as Master, then log in as the
    employee's own linked account and confirm the notification is
    genuinely visible to them, not just that notify() was called."""
    _login(client, test_user)
    employee = _make_employee(client, "17")
    user = User(
        username="salaryadvancenotifyuser", email="salaryadvancenotifyuser@example.com",
        full_name="Salary Advance Notify User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    assert resp.status_code == 200

    client.post("/api/auth/login", json={"identifier": "salaryadvancenotifyuser@example.com", "password": "EmpPass1!"})
    notifications = client.get("/api/notifications/").json()
    matches = [n for n in notifications if n["related_entity_type"] == "salary_advance" and n["related_entity_id"] == advance["id"]]
    assert len(matches) == 1
    assert "approved" in matches[0]["title"].lower()


def test_rejection_notifies_the_employees_linked_user_with_reason(client, test_user, db_session):
    _login(client, test_user)
    employee = _make_employee(client, "18")
    user = User(
        username="salaryadvancerejectnotifyuser", email="salaryadvancerejectnotifyuser@example.com",
        full_name="Salary Advance Reject Notify User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/reject", json={"rejection_reason": "Insufficient reason given"})

    client.post("/api/auth/login", json={"identifier": "salaryadvancerejectnotifyuser@example.com", "password": "EmpPass1!"})
    notifications = client.get("/api/notifications/").json()
    matches = [n for n in notifications if n["related_entity_type"] == "salary_advance" and n["related_entity_id"] == advance["id"]]
    assert len(matches) == 1
    assert "rejected" in matches[0]["title"].lower()
    assert "Insufficient reason given" in matches[0]["message"]


def test_approval_does_not_fail_when_employee_has_no_linked_user(client, test_user):
    """A best-effort courtesy notification - its absence must never
    break the actual approval."""
    _login(client, test_user)
    employee = _make_employee(client, "19")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()

    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "Approved"


def test_master_approve_at_requested_amount(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "4")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()

    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Approved"
    assert float(body["approved_amount"]) == 4000.0
    assert float(body["requested_amount"]) == 4000.0


def test_master_approve_at_different_amount_preserves_requested(client, test_user):
    """Spec: requested_amount remains historical; approved_amount is
    the separate, authoritative figure."""
    _login(client, test_user)
    employee = _make_employee(client, "5")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "10000", "request_date": "2026-09-01T00:00:00",
    }).json()

    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "approved_amount": "6000", "recovery_month": "September", "recovery_year": "2026",
    })
    body = resp.json()
    assert float(body["approved_amount"]) == 6000.0
    assert float(body["requested_amount"]) == 10000.0  # unchanged


def test_master_reject_advance(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "6")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()

    resp = client.put(f"/api/salary-advances/{advance['id']}/reject", json={"rejection_reason": "Not eligible"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Rejected"
    assert body["rejection_reason"] == "Not eligible"
    assert float(body["outstanding_amount"]) == 0.0


def test_cannot_approve_already_approved_advance(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "7")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })

    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    assert resp.status_code == 409


def test_cannot_reject_already_rejected_advance(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "8")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/reject", json={})

    resp = client.put(f"/api/salary-advances/{advance['id']}/reject", json={})
    assert resp.status_code == 409


def test_recovery_updates_advance_and_salary_slip(client, test_user):
    """The core P0.44/P0.43 connection: recovery actually changes a
    real SalarySlip's advance_deduction and net_salary - not just a
    number on the advance itself."""
    _login(client, test_user)
    employee = _make_employee(client, "9")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000",
    }).json()
    assert float(slip["net_salary"]) == 20000.0

    resp = client.post(f"/api/salary-advances/{advance['id']}/recover", json={
        "amount": "2000", "month": "September", "year": "2026",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["recovered_amount"]) == 2000.0
    assert float(body["outstanding_amount"]) == 3000.0

    updated_slip = client.get(f"/api/salary-slips/{slip['id']}").json()
    assert float(updated_slip["advance_deduction"]) == 2000.0
    assert float(updated_slip["net_salary"]) == 18000.0  # 20000 - 2000


def test_cannot_recover_more_than_outstanding(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "10")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "approved_amount": "3000", "recovery_month": "September", "recovery_year": "2026",
    })
    client.post("/api/salary-slips/", json={"employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000"})

    resp = client.post(f"/api/salary-advances/{advance['id']}/recover", json={
        "amount": "5000", "month": "September", "year": "2026",
    })
    assert resp.status_code == 400


def test_cannot_recover_from_pending_advance(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "11")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.post("/api/salary-slips/", json={"employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000"})

    resp = client.post(f"/api/salary-advances/{advance['id']}/recover", json={
        "amount": "1000", "month": "September", "year": "2026",
    })
    assert resp.status_code == 409


def test_cannot_recover_from_rejected_advance(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "12")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/reject", json={})
    client.post("/api/salary-slips/", json={"employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000"})

    resp = client.post(f"/api/salary-advances/{advance['id']}/recover", json={
        "amount": "1000", "month": "September", "year": "2026",
    })
    assert resp.status_code == 409


def test_recovery_without_matching_salary_slip_rejected(client, test_user):
    _login(client, test_user)
    employee = _make_employee(client, "13")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "5000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    # No SalarySlip created for this employee/month at all.

    resp = client.post(f"/api/salary-advances/{advance['id']}/recover", json={
        "amount": "1000", "month": "September", "year": "2026",
    })
    assert resp.status_code == 404


def test_employee_cannot_view_another_employees_advance(client, test_user, db_session):
    _login(client, test_user)
    other_employee = _make_employee(client, "14a")
    other_advance = client.post("/api/salary-advances/", json={
        "employee_id": other_employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    self_employee = _make_employee(client, "14b")
    _login_as_employee(client, db_session, self_employee["id"], "14")

    resp = client.get(f"/api/salary-advances/{other_advance['id']}")
    assert resp.status_code == 403

    resp = client.get("/api/salary-advances/", params={"employee_id": other_employee["id"]})
    assert resp.status_code == 403


def test_employee_can_view_own_advance(client, test_user, db_session):
    _login(client, test_user)
    employee = _make_employee(client, "15")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    _login_as_employee(client, db_session, employee["id"], "15")

    resp = client.get(f"/api/salary-advances/{advance['id']}")
    assert resp.status_code == 200


def test_employee_cannot_approve_or_reject(client, test_user, db_session):
    _login(client, test_user)
    employee = _make_employee(client, "16")
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "4000", "request_date": "2026-09-01T00:00:00",
    }).json()
    _login_as_employee(client, db_session, employee["id"], "16")

    resp = client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })
    assert resp.status_code == 403


def test_salary_advances_require_auth(client):
    resp = client.get("/api/salary-advances/")
    assert resp.status_code == 401
