"""Tests for GET /api/candidates/workspace - the compact Candidates
command-center workspace endpoint added to extend the approved Orders/
Clients workspace layout to Candidates. Covers response shape, search,
status/position filters, pagination, selected-record detail (including
interview history read from the existing Interview table), the
detail_only fast path, summary aggregates, and the master-only
permission that already governs the whole candidates_router."""
from tests.helpers import _login
from app.platform.security import hash_password
from app.modules.auth.auth import User

CANDIDATE_STATUSES = ["Applied", "Shortlisted", "Selected", "Rejected"]


def _make_candidate(client, **overrides):
    payload = {"name": "Workspace Test Candidate", "position": "Carpenter"}
    payload.update(overrides)
    return client.post("/api/candidates/", json=payload).json()


def test_candidates_workspace_response_shape(client, test_user):
    _login(client, test_user)
    _make_candidate(client, name="Shape Check Candidate")

    resp = client.get("/api/candidates/workspace")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"summary", "candidates", "selected_candidate"}
    assert set(data["candidates"].keys()) == {"items", "total_count", "limit", "offset"}
    assert "total_candidates" in data["summary"]
    assert "hiring_pipeline" in data["summary"] and "interview_activity" in data["summary"]
    assert data["selected_candidate"] is None


def test_candidates_workspace_search_matches_list_filter(client, test_user):
    _login(client, test_user)
    _make_candidate(client, name="Zanzibar Applicant", email="zanzibar.applicant@example.com", phone="9990001112")
    _make_candidate(client, name="Unrelated Applicant")

    resp = client.get("/api/candidates/workspace", params={"search": "Zanzibar"}).json()
    names = {c["name"] for c in resp["candidates"]["items"]}
    assert "Zanzibar Applicant" in names
    assert "Unrelated Applicant" not in names

    by_email = client.get("/api/candidates/workspace", params={"search": "zanzibar.applicant"}).json()
    assert any(c["name"] == "Zanzibar Applicant" for c in by_email["candidates"]["items"])


def test_candidates_workspace_status_and_position_filters(client, test_user):
    _login(client, test_user)
    candidate = _make_candidate(client, name="Status Filter Candidate", position="Finisher")
    client.put(f"/api/candidates/{candidate['id']}", json={"status": "Shortlisted"})
    _make_candidate(client, name="Other Status Candidate", position="Painter")

    resp = client.get("/api/candidates/workspace", params={"status": "Shortlisted"}).json()
    names = {c["name"] for c in resp["candidates"]["items"]}
    assert "Status Filter Candidate" in names
    assert "Other Status Candidate" not in names

    by_position = client.get("/api/candidates/workspace", params={"position": "Painter"}).json()
    assert any(c["name"] == "Other Status Candidate" for c in by_position["candidates"]["items"])


def test_candidates_workspace_only_uses_approved_statuses(client, test_user):
    """Candidate statuses are exactly Applied/Shortlisted/Selected/
    Rejected - nothing invented. The status_breakdown must only ever
    list these four."""
    _login(client, test_user)
    _make_candidate(client, name="Status Breakdown Candidate")

    resp = client.get("/api/candidates/workspace").json()
    breakdown_statuses = {row["status"] for row in resp["summary"]["overview"]["status_breakdown"]}
    assert breakdown_statuses == set(CANDIDATE_STATUSES)


def test_candidates_workspace_pagination_is_bounded(client, test_user):
    _login(client, test_user)
    for i in range(7):
        _make_candidate(client, name=f"Paginate Candidate {i}")

    resp = client.get("/api/candidates/workspace", params={"search": "Paginate Candidate", "limit": 3, "offset": 0}).json()
    assert resp["candidates"]["total_count"] == 7
    assert len(resp["candidates"]["items"]) == 3

    page2 = client.get("/api/candidates/workspace", params={"search": "Paginate Candidate", "limit": 3, "offset": 3}).json()
    page1_ids = {c["id"] for c in resp["candidates"]["items"]}
    page2_ids = {c["id"] for c in page2["candidates"]["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_candidates_workspace_selected_candidate_includes_interview_history(client, test_user):
    _login(client, test_user)
    candidate = _make_candidate(client, name="Selected Detail Candidate")
    client.post("/api/interviews/", json={
        "candidate_id": candidate["id"], "round": "Technical", "scheduled_date": "2026-09-20T10:00:00",
        "interviewer": "HR Manager",
    })

    resp = client.get("/api/candidates/workspace", params={"selected_candidate_id": candidate["id"]}).json()
    selected = resp["selected_candidate"]
    assert selected is not None
    assert selected["id"] == candidate["id"]
    assert len(selected["interviews"]) == 1
    assert selected["interviews"][0]["round"] == "Technical"


def test_candidates_workspace_selected_candidate_missing_returns_none(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/candidates/workspace", params={"selected_candidate_id": 999999}).json()
    assert resp["selected_candidate"] is None


def test_candidates_workspace_detail_only_skips_summary_and_list(client, test_user):
    _login(client, test_user)
    candidate = _make_candidate(client, name="Detail Only Candidate")

    resp = client.get(
        "/api/candidates/workspace",
        params={"selected_candidate_id": candidate["id"], "detail_only": True},
    ).json()
    assert resp["summary"] is None
    assert resp["candidates"] is None
    assert resp["selected_candidate"] is not None
    assert resp["selected_candidate"]["id"] == candidate["id"]


def test_candidates_workspace_summary_counts_are_authoritative(client, test_user):
    _login(client, test_user)
    candidate = _make_candidate(client, name="Summary Count Candidate")
    client.put(f"/api/candidates/{candidate['id']}", json={"status": "Selected"})
    client.post("/api/interviews/", json={
        "candidate_id": candidate["id"], "round": "HR", "scheduled_date": "2026-09-21T10:00:00",
        "interviewer": "HR Manager",
    })

    resp = client.get("/api/candidates/workspace").json()
    summary = resp["summary"]
    assert summary["selected_count"] >= 1
    assert summary["interview_activity"]["total_interviews"] >= 1


def test_candidates_workspace_requires_master_role(client, test_user, db_session):
    """The whole candidates_router is master-only (require_role("master")) -
    the workspace endpoint must enforce the exact same restriction, never
    a looser one."""
    _login(client, test_user)
    _make_candidate(client, name="Permission Check Candidate")

    non_master = User(
        username="candidatewsuser", email="candidatewsuser@example.com", full_name="Candidate WS User",
        password_hash=hash_password("NonMasterPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(non_master)
    db_session.commit()
    login_resp = client.post("/api/auth/login", json={"identifier": "candidatewsuser@example.com", "password": "NonMasterPass1!"})
    assert login_resp.status_code == 200

    resp = client.get("/api/candidates/workspace")
    assert resp.status_code == 403
