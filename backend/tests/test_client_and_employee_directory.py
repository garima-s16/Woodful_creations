def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_client_export_returns_xlsx(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Mhow Export Client", "phone": "9000000001", "city": "Mhow"})

    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.content) > 0


def test_client_export_respects_search_filter(client, test_user):
    """search 'Mhow' -> export only matches search 'Mhow' -> list, same filter."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Mhow Client One", "phone": "9000000002"})
    client.post("/api/clients/", json={"name": "Indore Client Two", "phone": "9000000003"})

    list_resp = client.get("/api/clients/?search=Mhow")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    export_resp = client.get("/api/reports/clients.xlsx?search=Mhow")
    assert export_resp.status_code == 200


def test_client_city_and_status_persist(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={
        "name": "City Status Test Client", "city": "Mhow", "status": "Active",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["city"] == "Mhow"
    assert body["status"] == "Active"


def _create_employee(client, name="Directory Test Employee", **overrides):
    payload = {"name": name, "department": "Production", "monthly_salary": "30000.00"}
    payload.update(overrides)
    resp = client.post("/api/employees/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_employee_directory_fields_persist(client, test_user):
    _login(client, test_user)
    emp = _create_employee(
        client, name="Pankaj Sharma", designation="Site Supervisor",
        email="pankaj@example.com", manager="Garima",
    )
    assert emp["designation"] == "Site Supervisor"
    assert emp["email"] == "pankaj@example.com"
    assert emp["manager"] == "Garima"


def test_employee_email_is_validated(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Bad Email Employee", "email": "not-an-email", "monthly_salary": "20000.00",
    })
    assert resp.status_code == 422


def test_employee_search_by_name(client, test_user):
    _login(client, test_user)
    _create_employee(client, name="Pankaj Kumar")
    _create_employee(client, name="Nikhil Verma")

    resp = client.get("/api/employees/?search=Pankaj")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()]
    assert "Pankaj Kumar" in names
    assert "Nikhil Verma" not in names


def test_employee_directory_export_returns_xlsx(client, test_user):
    _login(client, test_user)
    _create_employee(client, name="Export Test Employee")

    resp = client.get("/api/reports/employees.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.content) > 0
