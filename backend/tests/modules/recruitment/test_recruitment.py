"""Recruitment tests: resume upload (Priority 7 regression -
MAX_UPLOAD_SIZE/UPLOAD_DIRECTORY/ALLOWED_EXTENSIONS existed in
config.py but were never wired into any actual route before this),
interview feedback (ratings/recommendation persistence and
validation), and the candidate/interview creation flow."""
import io
from tests.helpers import _login


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

# ===========================================================================
# Interview feedback (from test_admin_and_ai_gateway.py, itself from
# test_interview_feedback.py)
# ===========================================================================
def test_feedback_persists_and_is_returned_by_api(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Feedback Test Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00", "interviewer": "Garima Sharma",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={
        "overall_rating": 4, "technical_rating": 5, "communication_rating": 3, "culture_fit_rating": 4,
        "strengths": "Strong technical fundamentals", "weaknesses": "Limited leadership experience",
        "observations": "Confident, asked good questions", "recommendation": "Hire", "status": "Completed",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_rating"] == 4
    assert body["recommendation"] == "Hire"
    assert body["strengths"] == "Strong technical fundamentals"

    # Confirm it's actually persisted, not just echoed back from the request.
    refetched = client.get("/api/interviews/", params={"candidate_id": candidate_id}).json()
    assert refetched[0]["recommendation"] == "Hire"
    assert refetched[0]["overall_rating"] == 4


def test_rating_out_of_range_rejected(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Rating Range Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={"overall_rating": 7})
    assert resp.status_code == 422


def test_invalid_recommendation_rejected(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Bad Recommendation Candidate"}).json()["id"]
    interview = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    }).json()

    resp = client.put(f"/api/interviews/{interview['id']}", json={"recommendation": "Maybe"})
    assert resp.status_code == 422


def test_interview_still_gets_business_id(client, test_user):
    _login(client, test_user)
    candidate_id = client.post("/api/candidates/", json={"name": "Interview Business ID Candidate"}).json()["id"]
    resp = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "scheduled_date": "2026-08-14T10:00:00",
    })
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10

# ===========================================================================

# ===========================================================================
# Candidate/interview flow (from test_admin_and_ai_gateway.py's former
# test_estimates_hr.py section)
# ===========================================================================
def test_candidate_and_interview_flow(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Test Candidate", "position": "CNC Operator"})
    assert resp.status_code == 201
    candidate_id = resp.json()["id"]

    resp = client.post("/api/interviews/", json={
        "candidate_id": candidate_id, "round": "Round 1",
        "scheduled_date": "2026-08-15T10:00:00", "interviewer": "Nikhil",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Scheduled"


def test_candidates_require_master_or_manager(client):
    resp = client.get("/api/candidates/")
    assert resp.status_code == 401
