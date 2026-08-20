"""Tests for Family 2 (CRM): duplicate-client detection (non-blocking,
fuzzy-matched) and client document upload/download/delete with
object-level authorization (document_id must match client_id, not
just exist)."""
import io


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_duplicate_check_finds_substring_match(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Sanket Kumar"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Sanket"})
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Sanket Kumar" in names


def test_duplicate_check_does_not_flag_genuinely_different_names(client, test_user):
    """Regression guard for the false positive caught while building
    this - two genuinely different approved names must not collide."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Ashu"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Ishu"})
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Ashu" not in names


def test_duplicate_check_catches_typo_variant(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Sanket"})
    resp = client.get("/api/clients/check-duplicates", params={"name": "Sankett"})
    names = [d["name"] for d in resp.json()["possible_duplicates"]]
    assert "Sanket" in names


def test_upload_and_download_client_document(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Document Upload Test Client"}).json()["id"]
    files = {"file": ("contract.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")}
    upload = client.post(f"/api/clients/{client_id}/documents", files=files, data={"description": "Signed contract"})
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    download = client.get(f"/api/clients/{client_id}/documents/{doc_id}/download")
    assert download.status_code == 200


def test_document_upload_rejects_disallowed_extension(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Bad Extension Test Client"}).json()["id"]
    files = {"file": ("virus.exe", io.BytesIO(b"not a real exe"), "application/octet-stream")}
    resp = client.post(f"/api/clients/{client_id}/documents", files=files)
    assert resp.status_code == 400


def test_document_upload_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Doc Upload Permission Client"}).json()["id"]
    employee = client.post("/api/employees/", json={"name": "Doc Upload Permission Employee"}).json()
    user = User(
        username="docuploadpermuser", email="docuploadpermuser@example.com",
        full_name="Doc Upload Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "docuploadpermuser@example.com", "password": "EmpPass1!"})

    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post(f"/api/clients/{client_id}/documents", files=files)
    assert resp.status_code == 403


def test_document_download_rejects_mismatched_client_id(client, test_user):
    """The core IDOR protection - a real document_id under the WRONG
    client_id in the URL must not be accessible."""
    _login(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "IDOR Test Client A"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "IDOR Test Client B"}).json()["id"]
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real content"), "application/pdf")}
    doc = client.post(f"/api/clients/{client_a}/documents", files=files).json()

    resp = client.get(f"/api/clients/{client_b}/documents/{doc['id']}/download")
    assert resp.status_code == 404


def test_client_activity_accepts_follow_up_date(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Follow Up Field Test Client"}).json()["id"]
    resp = client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-19T00:00:00",
        "summary": "Discussed pricing", "follow_up_date": "2026-08-25T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["follow_up_date"] is not None
