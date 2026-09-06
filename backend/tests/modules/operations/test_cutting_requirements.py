"""Tests for CuttingRequirement (P0.3 section 25) - a single part that
needs to be cut from a material sheet, with real dimensions/grain/
rotation data, never free text. Creating one must never touch
Material.current_stock - it is a plan, not a consumption event."""
from tests.helpers import _login


def _make_job(client):
    return client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()


def test_create_and_get_cutting_requirement(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req Sheet", "unit": "Sheets", "opening_stock": "10"}).json()

    resp = client.post("/api/cutting-requirements/", json={
        "production_job_id": job["id"], "material_id": material["id"], "part_name": "Side Panel",
        "quantity": 4, "length_mm": "600", "width_mm": "400", "thickness_mm": "18",
        "grain_direction": "Length", "rotation_allowed": False, "kerf_mm": "3.2",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["part_name"] == "Side Panel"
    assert body["material_name"] == "Cutting Req Sheet"
    assert body["rotation_allowed"] is False
    assert float(body["length_mm"]) == 600.0

    resp = client.get(f"/api/cutting-requirements/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["part_name"] == "Side Panel"


def test_creating_cutting_requirement_never_touches_stock(client, test_user):
    """The explicit brief requirement: this is a plan, not a
    consumption event."""
    _login(client, test_user)
    job = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req Stock Sheet", "unit": "Sheets", "opening_stock": "10"}).json()

    client.post("/api/cutting-requirements/", json={
        "production_job_id": job["id"], "material_id": material["id"], "part_name": "Top",
        "quantity": 2, "length_mm": "500", "width_mm": "300",
    })

    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert float(unchanged["current_stock"]) == 10.0


def test_dimensions_must_be_positive(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req Bad Dim Sheet", "unit": "Sheets", "opening_stock": "10"}).json()

    resp = client.post("/api/cutting-requirements/", json={
        "production_job_id": job["id"], "material_id": material["id"], "part_name": "Bad Part",
        "length_mm": "0", "width_mm": "300",
    })
    assert resp.status_code == 422


def test_unknown_production_job_rejected(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={"name": "Cutting Req Orphan Sheet", "unit": "Sheets", "opening_stock": "10"}).json()

    resp = client.post("/api/cutting-requirements/", json={
        "production_job_id": 999999, "material_id": material["id"], "part_name": "Orphan Part",
        "length_mm": "500", "width_mm": "300",
    })
    assert resp.status_code == 404


def test_list_filters_by_production_job(client, test_user):
    _login(client, test_user)
    job_a = _make_job(client)
    job_b = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req Filter Sheet", "unit": "Sheets", "opening_stock": "10"}).json()
    client.post("/api/cutting-requirements/", json={
        "production_job_id": job_a["id"], "material_id": material["id"], "part_name": "Job A Part",
        "length_mm": "500", "width_mm": "300",
    })
    client.post("/api/cutting-requirements/", json={
        "production_job_id": job_b["id"], "material_id": material["id"], "part_name": "Job B Part",
        "length_mm": "500", "width_mm": "300",
    })

    resp = client.get("/api/cutting-requirements/", params={"production_job_id": job_a["id"]})
    parts = [r["part_name"] for r in resp.json()]
    assert "Job A Part" in parts
    assert "Job B Part" not in parts


def test_update_and_delete_cutting_requirement(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req Update Sheet", "unit": "Sheets", "opening_stock": "10"}).json()
    requirement = client.post("/api/cutting-requirements/", json={
        "production_job_id": job["id"], "material_id": material["id"], "part_name": "Original Name",
        "length_mm": "500", "width_mm": "300",
    }).json()

    resp = client.put(f"/api/cutting-requirements/{requirement['id']}", json={"part_name": "Renamed Part", "quantity": 3})
    assert resp.status_code == 200
    assert resp.json()["part_name"] == "Renamed Part"
    assert resp.json()["quantity"] == 3

    resp = client.delete(f"/api/cutting-requirements/{requirement['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/cutting-requirements/{requirement['id']}").status_code == 404


def test_cutting_requirements_are_master_only_to_write(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    _login(client, test_user)
    job = _make_job(client)
    material = client.post("/api/materials/", json={"name": "Cutting Req RBAC Sheet", "unit": "Sheets", "opening_stock": "10"}).json()
    employee = User(
        username="cuttingrequser", email="cuttingrequser@example.com", full_name="Cutting Req Employee",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "cuttingrequser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/cutting-requirements/", json={
        "production_job_id": job["id"], "material_id": material["id"], "part_name": "Employee Part",
        "length_mm": "500", "width_mm": "300",
    })
    assert resp.status_code == 403
    # Reading is fine for any authenticated employee.
    assert client.get("/api/cutting-requirements/").status_code == 200


def test_cutting_requirements_require_auth(client):
    resp = client.get("/api/cutting-requirements/")
    assert resp.status_code == 401
