def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_client(client):
    resp = client.post("/api/clients/", json={"client_code": "CL-ACT", "name": "Activity Test Client"})
    return resp.json()["id"]


def test_log_and_list_client_activity(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)

    resp = client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-11T10:00:00",
        "summary": "Discussed dining table dimensions and delivery timeline.", "logged_by": "Garima",
    })
    assert resp.status_code == 201

    listed = client.get("/api/client-activities/", params={"client_id": client_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["activity_type"] == "Call"


def test_activities_filtered_by_client(client, test_user):
    _login(client, test_user)
    client_a = _create_client(client)
    client_b_resp = client.post("/api/clients/", json={"client_code": "CL-ACT-B", "name": "Other Client"})
    client_b = client_b_resp.json()["id"]

    client.post("/api/client-activities/", json={
        "client_id": client_a, "activity_type": "Meeting", "date": "2026-08-11T10:00:00", "summary": "Site visit.",
    })
    client.post("/api/client-activities/", json={
        "client_id": client_b, "activity_type": "Email", "date": "2026-08-11T11:00:00", "summary": "Sent quote.",
    })

    only_a = client.get("/api/client-activities/", params={"client_id": client_a})
    assert len(only_a.json()) == 1
    assert only_a.json()[0]["activity_type"] == "Meeting"


def test_client_activities_require_auth(client):
    resp = client.get("/api/client-activities/")
    assert resp.status_code == 401
