"""Regression tests for Priority 7's resume upload - MAX_UPLOAD_SIZE/
UPLOAD_DIRECTORY/ALLOWED_EXTENSIONS existed in config.py but were never
wired into any actual route before this."""
import io


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_pdf_resume_upload_succeeds(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "PDF Resume Candidate"}).json()["id"]

    fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content for testing")
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("resume.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["resume_original_filename"] == "resume.pdf"
    assert resp.json()["resume_content_type"] == "application/pdf"


def test_docx_resume_upload_succeeds(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "DOCX Resume Candidate"}).json()["id"]

    fake_docx = io.BytesIO(b"fake docx binary content")
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("resume.docx", fake_docx,
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200
    assert resp.json()["resume_original_filename"] == "resume.docx"


def test_doc_resume_upload_succeeds(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "DOC Resume Candidate"}).json()["id"]

    fake_doc = io.BytesIO(b"fake old-format doc content")
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("resume.doc", fake_doc, "application/msword")},
    )
    assert resp.status_code == 200


def test_disallowed_extension_rejected(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Bad Extension Candidate"}).json()["id"]

    fake_exe = io.BytesIO(b"not a real resume")
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("resume.exe", fake_exe, "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_mismatched_mime_type_rejected(client, test_user):
    """A .pdf extension with a MIME type that doesn't match any allowed
    resume type - the extension check alone isn't the only guard."""
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "MIME Mismatch Candidate"}).json()["id"]

    fake_file = io.BytesIO(b"disguised content")
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("resume.pdf", fake_file, "text/html")},
    )
    assert resp.status_code == 400


def test_uploaded_resume_can_be_downloaded(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Download Test Candidate"}).json()["id"]
    original_content = b"%PDF-1.4 the actual resume bytes"
    client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("my_resume.pdf", io.BytesIO(original_content), "application/pdf")},
    )

    resp = client.get(f"/api/candidates/{candidate_id}/resume")
    assert resp.status_code == 200
    assert resp.content == original_content
    assert "my_resume.pdf" in resp.headers.get("content-disposition", "")


def test_replacing_resume_removes_the_old_file_reference(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Replace Resume Candidate"}).json()["id"]
    client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("first.pdf", io.BytesIO(b"first version"), "application/pdf")},
    )
    resp = client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("second.pdf", io.BytesIO(b"second version"), "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["resume_original_filename"] == "second.pdf"

    download = client.get(f"/api/candidates/{candidate_id}/resume")
    assert download.content == b"second version"


def test_download_with_no_resume_uploaded_gives_clear_404(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "No Resume Candidate"}).json()["id"]
    resp = client.get(f"/api/candidates/{candidate_id}/resume")
    assert resp.status_code == 404


def test_delete_resume_removes_it(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Delete Resume Candidate"}).json()["id"]
    client.post(
        f"/api/candidates/{candidate_id}/resume",
        files={"file": ("to_delete.pdf", io.BytesIO(b"content"), "application/pdf")},
    )
    resp = client.delete(f"/api/candidates/{candidate_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["resume_original_filename"] is None

    download = client.get(f"/api/candidates/{candidate_id}/resume")
    assert download.status_code == 404
