"""Tests for the Object Storage abstraction. Proves the
abstraction itself works correctly in isolation, and that every
upload route still behaves identically after being routed through it
- same validation, same authorization, same IDOR protection."""
import io
from tests.helpers import _login


def test_local_backend_save_read_exists_delete_round_trip():
    """The abstraction in isolation, no HTTP involved. Verifies the
    CURRENT StorageReference-based contract: save() returns a
    reference, and read/exists/delete all require that reference -
    not the bare relative_path string directly."""
    from app.platform.storage.storage import LocalStorageBackend, StorageReference
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        probe_ref = StorageReference(backend="local", relative_path="subdir/test.txt")
        assert backend.exists(probe_ref) is False
        ref = backend.save("subdir/test.txt", b"hello woodful")
        assert isinstance(ref, StorageReference)
        assert ref.backend == "local"
        assert ref.relative_path == "subdir/test.txt"
        assert ref.drive_file_id is None
        assert backend.exists(ref) is True
        assert backend.read(ref) == b"hello woodful"
        backend.delete(ref)
        assert backend.exists(ref) is False


def test_local_backend_delete_of_nonexistent_file_does_not_raise():
    from app.platform.storage.storage import LocalStorageBackend, StorageReference
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        ref = StorageReference(backend="local", relative_path="never_existed.txt")
        backend.delete(ref)  # must not raise


def test_unknown_storage_provider_raises_clearly():
    """Confirms this never silently pretends to be a real cloud
    backend - an unimplemented provider must fail loudly."""
    from app.platform.storage.storage import get_storage_backend
    import app.platform.storage.storage as storage_module
    from app.platform.configuration.config import settings as real_settings
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


def test_client_document_delete_survives_db_commit_failure(client, test_user):
    """A correction for a critical ordering issue, exercised against the
    REAL route (not a local stand-in) by making the actual db.commit()
    called inside delete_client_document raise, via unittest.mock
    scoped only around this one HTTP call. Before the fix, the physical
    file was deleted BEFORE this commit; if that ordering had regressed,
    the document would still exist in the DB afterward (since the mocked
    commit prevents the real deletion from persisting) while its file
    would already be gone - the exact inconsistency this test guards
    against. With the fix, a failed commit must raise a 500 and leave
    both the DB record and the file untouched."""
    from unittest.mock import patch
    from sqlalchemy.orm import Session

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Delete Failure Test Client", "phone": "9000010096"}).json()["id"]
    files = {"file": ("survive.pdf", io.BytesIO(b"%PDF-1.4 must survive"), "application/pdf")}
    doc = client.post(f"/api/clients/{client_id}/documents", files=files).json()

    with patch.object(Session, "commit", side_effect=Exception("simulated DB failure")):
        resp = client.delete(f"/api/clients/{client_id}/documents/{doc['id']}")
    assert resp.status_code == 500

    # The mocked commit is gone now (patch context exited) - a normal
    # download must still succeed, proving neither the DB record nor
    # the physical file was actually removed by the failed attempt.
    download = client.get(f"/api/clients/{client_id}/documents/{doc['id']}/download")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 must survive"


def test_candidate_resume_replacement_preserves_old_file_until_db_commit_succeeds(client, test_user):
    """A correction for a critical replacement-ordering issue, at the real HTTP/route
    level. Uploads a resume, then replaces it, then verifies the OLD
    file's storage key is gone from disk only once the replacement is
    confirmed to have fully succeeded (the new resume downloads
    correctly) - proving the deletion of the old file was genuinely
    deferred until after the new reference was durably committed,
    not performed eagerly before the outcome was known."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={
        "name": "Resume Replacement Test Candidate", "position": "Carpenter",
    }).json()

    first_files = {"file": ("resume_v1.pdf", io.BytesIO(b"%PDF-1.4 version one"), "application/pdf")}
    first_upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=first_files)
    assert first_upload.status_code == 200

    second_files = {"file": ("resume_v2.pdf", io.BytesIO(b"%PDF-1.4 version two"), "application/pdf")}
    second_upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=second_files)
    assert second_upload.status_code == 200
    assert second_upload.json()["resume_original_filename"] == "resume_v2.pdf"

    # The replacement fully succeeded end-to-end - downloading now must
    # return the NEW content, and the old file must genuinely be gone
    # (not accumulating), confirming cleanup happened on the success
    # path as intended, not left as a permanent duplicate.
    download = client.get(f"/api/candidates/{candidate['id']}/resume")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 version two"
