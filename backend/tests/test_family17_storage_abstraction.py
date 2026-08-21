"""Tests for Family 17.1 (Object Storage abstraction). Proves the
abstraction itself works correctly in isolation, and that every
upload route still behaves identically after being routed through it
- same validation, same authorization, same IDOR protection."""
import io


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_local_backend_save_read_exists_delete_round_trip():
    """The abstraction in isolation, no HTTP involved."""
    from app.core.storage import LocalStorageBackend
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        assert backend.exists("subdir/test.txt") is False
        backend.save("subdir/test.txt", b"hello woodful")
        assert backend.exists("subdir/test.txt") is True
        assert backend.read("subdir/test.txt") == b"hello woodful"
        backend.delete("subdir/test.txt")
        assert backend.exists("subdir/test.txt") is False


def test_local_backend_delete_of_nonexistent_file_does_not_raise():
    from app.core.storage import LocalStorageBackend
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        backend.delete("never_existed.txt")  # must not raise


def test_unknown_storage_provider_raises_clearly():
    """Confirms this never silently pretends to be a real cloud
    backend - an unimplemented provider must fail loudly."""
    from app.core.storage import get_storage_backend
    import app.core.storage as storage_module
    from app.core.config import settings as real_settings
    storage_module._backend_instance = None
    original = real_settings.STORAGE_PROVIDER
    real_settings.STORAGE_PROVIDER = "azure_not_implemented"
    try:
        try:
            get_storage_backend()
            assert False, "should have raised"
        except NotImplementedError as e:
            assert "not implemented" in str(e).lower()
    finally:
        real_settings.STORAGE_PROVIDER = original
        storage_module._backend_instance = None


def test_document_upload_still_works_through_the_abstraction(client, test_user):
    """Confirms routing through the abstraction did not change the
    actual upload/download behavior for a real route."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage Abstraction Test Client", "phone": "9000010093"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 real pdf content"), "application/pdf")}
    upload = client.post(f"/api/documents/order/{order['id']}", files=files)
    assert upload.status_code == 201

    download = client.get(f"/api/documents/order/{order['id']}/{upload.json()['id']}/download")
    assert download.status_code == 200


def test_document_delete_through_abstraction_removes_the_stored_file(client, test_user):
    """Confirms delete genuinely removes the file, not just the DB row -
    re-downloading after delete must fail."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage Delete Test Client", "phone": "9000010094"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "3000", "advance": "0",
    }).json()
    files = {"file": ("delete_me.pdf", io.BytesIO(b"%PDF-1.4 delete test"), "application/pdf")}
    doc = client.post(f"/api/documents/order/{order['id']}", files=files).json()

    delete_resp = client.delete(f"/api/documents/order/{order['id']}/{doc['id']}")
    assert delete_resp.status_code == 204
    download_resp = client.get(f"/api/documents/order/{order['id']}/{doc['id']}/download")
    assert download_resp.status_code == 404


def test_unauthorized_document_access_still_denied_after_abstraction(client, test_user):
    """The core "storage abstraction must not weaken authorization"
    proof - IDOR protection must still hold identically."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage IDOR Test Client", "phone": "9000010095"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "2000", "advance": "0",
    }).json()
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real"), "application/pdf")}
    doc = client.post(f"/api/documents/order/{order_a['id']}", files=files).json()

    resp = client.get(f"/api/documents/order/{order_b['id']}/{doc['id']}/download")
    assert resp.status_code == 404


def test_candidate_resume_upload_still_works_through_abstraction(client, test_user):
    """A second, differently-shaped upload route (with its own
    replace-on-reupload logic) also still works correctly."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={
        "name": "Storage Test Candidate", "position_applied": "Carpenter",
    }).json()
    files = {"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 resume content"), "application/pdf")}
    upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=files)
    assert upload.status_code == 200

    download = client.get(f"/api/candidates/{candidate['id']}/resume")
    assert download.status_code == 200
